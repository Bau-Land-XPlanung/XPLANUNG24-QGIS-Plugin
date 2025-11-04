from qgis.PyQt import QtCore, QtGui
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtGui import QIcon, QPalette
from qgis.PyQt.QtCore import QThread, pyqtSignal
from qgis.utils import iface
from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtGui import QIcon
import tempfile, requests, os, json

from ..utils.api import APILoadPlans, APIGetDownloadPlan
from ..utils.styles import apply_style_to_gml_layers


class PlanLoaderThread(QThread):
    """Thread für das Laden eines Plans"""
    finished = pyqtSignal(object, object)  # (plan, result)
    error = pyqtSignal(str)
    
    def __init__(self, cognito_session, plan):
        super().__init__()
        self.cognito_session = cognito_session
        self.plan = plan
        
    def run(self):
        try:
            plan_id = self.plan.get("id")
            if not plan_id:
                self.error.emit("Plan-ID fehlt.")
                return
                
            planObject = APIGetDownloadPlan(self.cognito_session, plan_id=plan_id)
            if not planObject:
                raise Exception("Kein API-Antwort gefunden.")
            
            plan_url = planObject.get("gml")
            gml_resp = requests.get(plan_url, timeout=60)
            gml_resp.raise_for_status()

            tmp = tempfile.NamedTemporaryFile(
                suffix=".gml",
                prefix=f"{plan_id or 'plan'}_",
                delete=False
            )
            tmp.write(gml_resp.content)
            tmp.flush()
            tmp.close()
            
            self.finished.emit(self.plan, {
                'tmp_path': tmp.name,
                'styles': planObject.get("styles"),
                'details': planObject.get("details", []),
                'plan_id': plan_id
            })
            
        except Exception as e:
            self.error.emit(str(e))


class PlansDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cognito_session=None):
        super().__init__(parent)
        
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        icon_path = os.path.abspath(icon_path)
        
        self.cognito_session = cognito_session
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle(" ")
        self.resize(640, 505)
        self.layout = QtWidgets.QVBoxLayout(self) 
        self.loader_thread = None
        
        # === Styles ===
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; padding:12px; }
            QTreeWidgetItem { background-color: white; font-weight:bold;} 
     
            QHeaderView::section {
                background-color: #FFF;    
                color: #000;               
                font-weight: bold;
                font-size: 13px;
                padding: 6px;
                border: none;
                border-bottom: 2px solid #eee;
            }
         
            QTreeWidget {
                background-color: #fff;
                gridline-color: #ccc;
                font-size: 12px;
            }
            
            QTreeWidget::item {
                background-color: white;
                border-bottom: 1px solid #eee;
            }
            QTreeWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }

            QTreeWidget::item {
                min-height: 28px;
                padding: 4px; 
            }
            
            QScrollBar:vertical {
                border: none;
                background: #fff;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }

            QScrollBar::handle:vertical {
                background: #000;
                min-height: 35px;
                border-radius: 4px;
            }

            QScrollBar::handle:vertical:hover {
                background: #888;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            QScrollBar:horizontal {
                border: none;
                background: #f0f0f0;
                height: 10px;
                margin: 0px 0px 0px 0px;
            }

            QScrollBar::handle:horizontal {
                background: #b0b0b0;
                min-width: 20px;
                border-radius: 4px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #888;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        
        # === HEADER ROW ===
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 20, 0)
        header_layout.setSpacing(20)
        text_container = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)
        description_label = QtWidgets.QLabel("Meine Pläne")
        description_label.setStyleSheet("font-size: 14px; color: #000; font-weight: bold;")
        description_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        description_label1 = QtWidgets.QLabel(
            "Welche Ihrer Pläne möchten Sie von XPLANUNG24 abrufen und in QGIS anzeigen?"
        )
        description_label1.setWordWrap(True)
        description_label1.setStyleSheet("font-size: 12px; color: #666; margin: 8px 0; font-weight: normal;")
        description_label1.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        text_layout.addWidget(description_label)
        text_layout.addWidget(description_label1)
        
        header_layout.addWidget(text_container, stretch=1)
        header_layout.addStretch()
        self.layout.addLayout(header_layout)
        
        # Table
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setColumnCount(3)
        self.tree_widget.setHeaderLabels(["Plan-ID", "Name", "Aktion"])
        self.tree_widget.setIndentation(0) 
        self.tree_widget.setColumnWidth(0, 100)
        self.tree_widget.setColumnWidth(1, 300)
        self.tree_widget.setColumnWidth(2, 150)
        self.tree_widget.setStyleSheet("color:#000; border:0px;")
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.layout.addWidget(self.tree_widget)
        
        # Loading Overlay
        self.loading_overlay = self.create_loading_overlay()
        self.loading_overlay.hide()
        
        self.load_plans()

    def create_loading_overlay(self):
        """Erstellt ein Loading-Overlay Widget"""
        overlay = QtWidgets.QWidget(self)
        overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 220);
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(overlay)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        
        label = QtWidgets.QLabel("Plan wird geladen...")
        label.setStyleSheet("font-size: 16px; font-weight: bold; color: #000; background: transparent;")
        label.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(label)
        
        return overlay

    def resizeEvent(self, event):
        """Stelle sicher, dass das Overlay immer die richtige Größe hat"""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.setGeometry(self.rect())

    def show_loading(self):
        """Zeigt den Loading-Indicator"""
        self.loading_overlay.setGeometry(self.rect())
        self.loading_overlay.raise_()
        self.loading_overlay.show()

    def hide_loading(self):
        """Versteckt den Loading-Indicator"""
        self.loading_overlay.hide()

    def load_plans(self):
        """Lädt die Pläne aus der API unter Verwendung des Cognito Tokens."""
        self.tree_widget.clear()

        try:
            plans = APILoadPlans(self.cognito_session)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"API-Fehler:\n{e}")
            return

        for plan in plans:
            item = QtWidgets.QTreeWidgetItem([
                str(plan.get("planId", "-")),
                plan.get("name", "-")
            ])
            item.setData(0, QtCore.Qt.UserRole, plan)
            self.tree_widget.addTopLevelItem(item)
          
            btn = QtWidgets.QPushButton("Anzeigen")
            btn.setStyleSheet("""
            QPushButton {
                cursor:pointer; 
                border: 1px solid #000; 
                padding: 8px 24px; 
                margin:2px; 
                font-size:12px;
                height:24px;
                border-radius:6px;
            }
            QPushButton:hover {
                background-color: #000;
                color: white;
                border: 1px solid #000;
            }
            QPushButton:pressed {
                background-color: #333;
                color: white;
            }""")
            btn.clicked.connect(lambda _, p=plan: self.load_plan_in_qgis(p))
            self.tree_widget.setItemWidget(item, 2, btn)

    def load_plan_in_qgis(self, plan):
        """Startet das Laden eines Plans im Hintergrund"""
        # Verhindere mehrfache Klicks
        if self.loader_thread and self.loader_thread.isRunning():
            return
            
        self.show_loading()
        
        # Thread erstellen und starten
        self.loader_thread = PlanLoaderThread(self.cognito_session, plan)
        self.loader_thread.finished.connect(self.on_plan_loaded)
        self.loader_thread.error.connect(self.on_plan_error)
        self.loader_thread.start()

    def on_plan_loaded(self, plan, result):
        """Wird aufgerufen wenn der Plan erfolgreich geladen wurde"""
        self.hide_loading()
        
        try:
            # Layer laden und Style anwenden
            loaded_layers = apply_style_to_gml_layers(
                result['tmp_path'], 
                plan.get("name", "Plan"), 
                result['styles']
            )
            
            # planId und Details speichern
            if result['plan_id'] and loaded_layers:
                for layer in loaded_layers:
                    if layer and layer.isValid():
                        layer.setCustomProperty("xplanung24_plan_id", result['plan_id'])
                        
                        if result['details']:
                            layer.setCustomProperty("xplanung24_details", json.dumps(result['details']))
                            print(f"✓ planId '{result['plan_id']}' und {len(result['details'])} Detail-Sections in Layer '{layer.name()}' gespeichert")
                        else:
                            print(f"✓ planId '{result['plan_id']}' in Layer '{layer.name()}' gespeichert (keine Details)")
            
            self.accept()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"{e}")

    def on_plan_error(self, error_msg):
        """Wird aufgerufen wenn ein Fehler beim Laden auftritt"""
        self.hide_loading()
        QtWidgets.QMessageBox.critical(self, "Fehler", error_msg)