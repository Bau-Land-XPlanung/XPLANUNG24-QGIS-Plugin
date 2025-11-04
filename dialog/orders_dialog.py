from qgis.PyQt import QtWidgets
from qgis.PyQt import QtCore, QtGui
import os
import requests
from datetime import datetime
from .order_detail_dialog import OrderDetailDialog
from ..utils.api import APILoadOrders

class OrdersDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cognito_session=None):
        super().__init__(parent)
        self.cognito_session = cognito_session

        self.setWindowTitle("Meine Aufträge")
        self.resize(800, 500)
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
                background-color: #0078d7;   /* blue selection */
                color: white;
            }

            QTreeWidget::item {
                min-height: 28px;
                padding: 4px; 
            }
            
            /* === Scrollbar styling === */
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
                height: 0px;  /* hide arrows */
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
        
        
        self.layout = QtWidgets.QVBoxLayout(self)
        
        # === HEADER ROW ===
        header_layout = QtWidgets.QHBoxLayout()
    
        # Left: description label
        description_label = QtWidgets.QLabel("Folgende Aufträge sind für Sie bei XPlanung24 hinterlegt.")
        description_label.setStyleSheet("font-size: 12px; color: #000;")
        description_label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
        
        # Right: logo
        logo_label = QtWidgets.QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.svg")
        logo_pixmap = QtGui.QPixmap(icon_path)
        logo_pixmap = logo_pixmap.scaledToHeight(28, QtCore.Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        header_layout.addWidget(description_label)
        header_layout.addStretch()
        header_layout.addWidget(logo_label)
        
        self.layout.addLayout(header_layout)

        # === TABLE ===
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setColumnCount(6)
        self.tree_widget.setHeaderLabels([
            "Erstellt am", "Auftragsbezeichnung", "Auftragsnr.",
            "Gemeinde", "Fortschritt", "Aktion"
        ])
        self.tree_widget.setIndentation(0)
        self.tree_widget.setColumnWidth(1, 150)
        self.tree_widget.setColumnWidth(2, 75)
        self.tree_widget.setColumnWidth(3, 150)
        self.tree_widget.setColumnWidth(4, 150)
        self.tree_widget.setColumnWidth(5, 100)
        self.tree_widget.setColumnWidth(6, 100)
        
        self.layout.addWidget(self.tree_widget)
        self.load_orders()

    def load_orders(self):
        self.tree_widget.clear()
        try:
            orders = APILoadOrders(self.cognito_session)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"API-Fehler:\n{e}")
            return

        for order in orders:
            # Mapping von Status-Feld zu Label
            status_map = {
                "draft": "Entwurf",
                "inTender": "In Ausschreibung",
                "contracted": "Beauftragt",
                "inDevelopment": "In Bearbeitung",
                "inReview": "Zur Abnahme",
                "completed": "Abgeschlossen"
            }
            stage_field = order.get("stage", "-")
            stage_label = status_map.get(stage_field, stage_field if stage_field != "-" else "-")

            created_at = order.get("createdAt", "-")
            if created_at and created_at != "-":
                try:
                    # Annahme: Timestamp ist in Millisekunden
                    created_at_dt = datetime.fromtimestamp(int(created_at) / 1000)
                    created_at_str = created_at_dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    created_at_str = str(created_at)
            else:
                created_at_str = "-"

            item = QtWidgets.QTreeWidgetItem([
                created_at_str,
                (order.get("planDetails") or {}).get("name", "-"),
                order.get("planId", "-"),
                ((order.get("planDetails") or {}).get("community") or {}).get("name", "-"),
                stage_label
            ])
            self.tree_widget.addTopLevelItem(item)

            btn = QtWidgets.QPushButton("Auftragsdetails")
            btn.setStyleSheet("""
            QPushButton {
                cursor:pointer; 
                border: 1px solid #000; 
                padding:2px; 
                margin:2px; 
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
            btn.clicked.connect(lambda _, o=order: self.view_order(o))
            self.tree_widget.setItemWidget(item, 5, btn)

    def view_order(self, order):
        dlg = OrderDetailDialog(parent=self, cognito_session=self.cognito_session, order_id=order.get("id"), plan_id=order.get("planId"))
        dlg.exec_()