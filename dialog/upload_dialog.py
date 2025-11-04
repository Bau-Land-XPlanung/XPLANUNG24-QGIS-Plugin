from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.PyQt.QtGui import QIcon, QPalette
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.utils import iface
from qgis.PyQt.QtGui import QIcon
import tempfile, requests, os, json
import os
import uuid
from ..utils.api import APILoadPlans, APIGetDownloadPlan, APIUploadPlan, APIGetUploadUrl
from ..utils.styles import apply_style_to_gml_layers

class UploadDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, cognito_session=None):
        super().__init__(parent)
        
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        icon_path = os.path.abspath(icon_path)
        
        self.cognito_session = cognito_session
        self.selected_file = None
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowTitle(" ")
        self.resize(640, 300)
        self.layout = QtWidgets.QVBoxLayout(self)

        # === Styles ===
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; padding: 12px; }
            QLabel { color: #000; font-size: 12px; }
            QLineEdit {
                padding: 8px; border: 1px solid #ccc; border-radius: 4px;
                background-color: white; color: #000; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #0078d7; }
            QPushButton {
                padding: 8px 16px; border: 1px solid #000; border-radius: 4px;
                background-color: white; color: #000; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #000; color: white; }
            QPushButton:pressed { background-color: #333; }
            QPushButton:disabled {
                background-color: #f0f0f0; color: #999; border: 1px solid #ddd;
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

        description_label = QtWidgets.QLabel("XPlanung-GML anzeigen")
        description_label.setStyleSheet("font-size: 14px; color: #000; font-weight: bold;")
        description_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        description_label1 = QtWidgets.QLabel(
            "Wählen Sie zunächst eine XPlan-GML-Datei, die in QGIS angezeigt werden soll. "
            "Ihr Plan wird anschließend unter „Meine Pläne“ gespeichert. Danach erstellen wir "
            "automatisch eine optimierte Darstellung für QGIS und zeigen diese direkt an."
        )
        description_label1.setWordWrap(True)
        description_label1.setStyleSheet("font-size: 12px; color: #666; margin: 8px 0; font-weight: normal;")
        description_label1.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        text_layout.addWidget(description_label)
        text_layout.addWidget(description_label1)
        

        header_layout.addWidget(text_container, stretch=1)
        header_layout.addStretch()
        self.layout.addLayout(header_layout)

        # === FILE SELECTION (no QGroupBox) ===
        file_layout = QtWidgets.QVBoxLayout()

        # Optional title label (instead of QGroupBox title)
        file_title = QtWidgets.QLabel("Datei wählen")
        file_title.setStyleSheet("font-weight: 600; font-size: 12px; margin-bottom: 6px;")
        file_layout.addWidget(file_title)

        # Horizontal layout for file path + button
        file_select_layout = QtWidgets.QHBoxLayout()
        self.file_path_input = QtWidgets.QLineEdit()
        self.file_path_input.setPlaceholderText("Keine GML ausgewählt...")
        self.file_path_input.setStyleSheet("border: 1px solid #000; border-radius: 6px; padding: 6px;")
        self.file_path_input.setReadOnly(True)

        self.browse_button = QtWidgets.QPushButton("Durchsuchen")
        self.browse_button.setStyleSheet("""
            QPushButton {
                background-color: #000;
                color: #fff;
                font-weight: normal;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #333; }
        """)
        self.browse_button.clicked.connect(self.select_file)

        file_select_layout.addWidget(self.file_path_input)
        file_select_layout.addWidget(self.browse_button)

        file_layout.addLayout(file_select_layout)
        self.layout.addLayout(file_layout)

        # === PLAN INFO (hidden) ===
        self.plan_name_input = QtWidgets.QLineEdit()
        self.plan_name_input.hide()  # invisible but used internally

        # === LOADING INDICATOR ===
        self.loading_container = QtWidgets.QWidget()
        loading_layout = QtWidgets.QHBoxLayout(self.loading_container)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(10)

        self.loading_label = QtWidgets.QLabel("Plan wird hochgeladen ... bitte warten")
        self.loading_label.setStyleSheet("font-size: 12px; color: #666;")

        self.loading_spinner = QtWidgets.QProgressBar()
        self.loading_spinner.setRange(0, 0)  # indefinite loading
        self.loading_spinner.setMaximumHeight(12)
        self.loading_spinner.setTextVisible(False)

        loading_layout.addWidget(self.loading_label)
        loading_layout.addWidget(self.loading_spinner)
        self.loading_container.hide()
        self.layout.addWidget(self.loading_container)

        # === BUTTONS ===
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.upload_button = QtWidgets.QPushButton("Hochladen")
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload_plan)
        self.upload_button.setStyleSheet("""
            QPushButton {
                padding: 8px 24px; background-color: #000; color: white; border: 1px solid #000;
            }
            QPushButton:hover { background-color: #333; border: 1px solid #333; color: white; }
            QPushButton:disabled { background-color: #eee; color: #666; border: 1px solid #ccc; }
        """)
        button_layout.addWidget(self.upload_button)
        self.layout.addStretch()
        self.layout.addLayout(button_layout)
        
        
        
        # Connect signals
        self.plan_name_input.textChanged.connect(self.validate_form)

    # === FILE SELECTION ===
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Plan-Datei auswählen",
            "",
            "XPlanung GML Dateien (*.gml);;Alle Dateien (*.*)"
        )

        if file_path:
            self.selected_file = file_path
            self.file_path_input.setText(file_path)

            # Auto-fill plan name internally
            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]
            self.plan_name_input.setText(name_without_ext)

            self.validate_form()

    # === FORM VALIDATION ===
    def validate_form(self):
        has_file = self.selected_file is not None
        has_name = len(self.plan_name_input.text().strip()) > 0
        self.upload_button.setEnabled(has_file and has_name)

    # === UPLOAD PROCESS ===
    def upload_plan(self):
        if not self.selected_file or not os.path.exists(self.selected_file):
            QtWidgets.QMessageBox.critical(self, "Fehler", "Keine gültige Datei ausgewählt.")
            return

        plan_name = self.plan_name_input.text().strip()
        if not plan_name:
            QtWidgets.QMessageBox.critical(self, "Fehler", "Planname fehlt.")
            return

        # Disable buttons during upload
        self.upload_button.setEnabled(False)
        self.browse_button.setEnabled(False)

        # Show loading indicator
        self.loading_container.show()
        self.loading_label.setText("Plan wird hochgeladen ... bitte warten")
        QtWidgets.QApplication.processEvents()

        try:
            with open(self.selected_file, 'rb') as f:
                file_content = f.read()

            # Upload to S3
            s3_key, plan_id = self.upload_to_s3(file_content, os.path.basename(self.selected_file))

            # Register plan in database
            status = APIUploadPlan(self.cognito_session, s3_key=s3_key, plan_id=plan_id)

            if status == False:
                raise Exception("Fehler bei der Plan-Registrierung.")
            elif status != True:
                plan_id = status

            # Success load Plan
            self.load_plan_in_qgis(plan_id)

            QtCore.QTimer.singleShot(800, self.accept)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Upload-Fehler", f"Fehler beim Hochladen:\n{str(e)}")
            self.loading_container.hide()

        finally:
            self.upload_button.setEnabled(True)
            self.browse_button.setEnabled(True)

    # === S3 UPLOAD ===
    def upload_to_s3(self, file_content, filename):
        # 1. Presigned URL von API holen (ohne filename Parameter)
        upload_data = APIGetUploadUrl(self.cognito_session)
        
        presigned_url = upload_data.get('uploadUrl')
        s3_key = upload_data.get('s3Key')
        plan_id = upload_data.get('planId')
        
        if not presigned_url or not plan_id:
            raise Exception("Keine Upload-URL oder Plan-ID von API erhalten")
        
        # 2. Datei mit presigned URL hochladen
        upload_response = requests.put(
            presigned_url,
            data=file_content,
            headers={'Content-Type': 'application/gml+xml'},
            timeout=120
        )
        
        if upload_response.status_code not in [200, 204]:
            raise Exception(f"S3 Upload fehlgeschlagen: {upload_response.status_code}")
        
        return s3_key, plan_id

    def load_plan_in_qgis(self, plan_id):

        
        if not plan_id:
            QtWidgets.QMessageBox.critical(self, "Fehler", "Plan-ID fehlt.")
            return

        try:
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
            tmp.close()

            styles = planObject.get("styles")
            details = planObject.get("details", [])  # 🔑 Details vom Server

            # Layer laden und Style anwenden
            loaded_layers = apply_style_to_gml_layers(
                tmp.name, 
                self.plan_name_input.text(), 
                styles
            )
            
            # 🔑 planId UND Details in allen geladenen Layern als Custom Property speichern
            if plan_id and loaded_layers:
                for layer in loaded_layers:
                    if layer and layer.isValid():
                        layer.setCustomProperty("xplanung24_plan_id", plan_id)
                        
                        # 🔑 Speichere Details als JSON-String
                        if details:
                            layer.setCustomProperty("xplanung24_details", json.dumps(details))
                            print(f"✓ planId '{plan_id}' und {len(details)} Detail-Sections in Layer '{layer.name()}' gespeichert")
                        else:
                            print(f"✓ planId '{plan_id}' in Layer '{layer.name()}' gespeichert (keine Details)")
            
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"{e}")