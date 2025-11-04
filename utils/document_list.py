from qgis.PyQt import QtWidgets, QtCore
import os
import tempfile, requests
from .api import APIGetOrderDocuments, APIGetDownloadByPath
from qgis.core import QgsVectorLayer
from qgis.utils import iface

class DocumentList(QtWidgets.QWidget):
    def __init__(self, cognito_session, order_id, review_id, parent=None):
        super().__init__(parent)
        self.cognito_session = cognito_session
        self.review_id = review_id
        self.order_id = order_id

        self.layout = QtWidgets.QVBoxLayout(self)
        self.setLayout(self.layout)

        self.load_documents()

    def load_documents(self):
        """Lädt Dokumente über die API und zeigt sie an"""
        try:
            documents = APIGetOrderDocuments(self.cognito_session, self.order_id, self.review_id)
        except Exception as e:
            documents = []

        # Vorherige Einträge entfernen
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not documents:
            self.layout.addWidget(QtWidgets.QLabel("Keine Dokumente vorhanden."))
            return

        for doc in documents:
            self.layout.addWidget(self._build_doc_row(doc))

    def _build_doc_row(self, doc: dict):
        """Erzeugt eine Zeile mit Dokumentnamen + Buttons"""
        row = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)

        # Name
        name_label = QtWidgets.QLabel(doc.get("fileName", "-"))
        h.addWidget(name_label, stretch=1)

        # Buttons
        path = doc.get("key", "")
        fileName = doc.get("fileName", "")
        if path.lower().endswith(".gml"):
            btn1 = QtWidgets.QPushButton("In QGIS importieren")
            btn1.clicked.connect(lambda _, fileName=fileName: self.import_gml(fileName))
            h.addWidget(btn1)
        btn = QtWidgets.QPushButton("Herunterladen")
        btn.clicked.connect(lambda _, fileName=fileName: self.download_file(fileName))
        h.addWidget(btn)

        return row

    def import_gml(self, fileName: str):
        try:
            s3_url = APIGetDownloadByPath(self.cognito_session, fileName, self.order_id, self.review_id)
            if not s3_url:
                raise Exception("Kein S3-Downloadlink in API-Antwort gefunden.")

            gml_resp = requests.get(s3_url, timeout=60)
            gml_resp.raise_for_status()

            tmp = tempfile.NamedTemporaryFile(
                suffix=".gml",
                prefix=f"{self.review_id}_",
                delete=False
            )
            tmp.write(gml_resp.content)
            tmp.close()

            layer_name = 'Abzunehmender Plan'
            vlayer = QgsVectorLayer(tmp.name, layer_name, "ogr")
            if not vlayer.isValid():
                vlayer = QgsVectorLayer(tmp.name, layer_name, "GMLAS")
            if not vlayer.isValid():
                raise Exception("Layer konnte nicht geladen werden.")

            iface.addVectorLayer(vlayer.source(), vlayer.name(), vlayer.providerType())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"{e}")

    def download_file(self, path: str):
        try:
            # S3-Download-Link von der API holen
            s3_url = APIGetDownloadByPath(self.cognito_session, path, self.order_id, self.review_id)
            if not s3_url:
                raise Exception("Kein S3-Downloadlink in API-Antwort gefunden.")

            # Dialog „Speichern unter“
            options = QtWidgets.QFileDialog.Options()
            options |= QtWidgets.QFileDialog.DontUseNativeDialog
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, 
                "Datei speichern unter", 
                path.split('/')[-1],  # Standardname aus dem Pfad
                "Alle Dateien (*)",
                options=options
            )

            if not save_path:
                return  # User hat abgebrochen

            # Datei herunterladen
            resp = requests.get(s3_url, timeout=60)
            resp.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(resp.content)

            QtWidgets.QMessageBox.information(self, "Erfolg", f"Datei gespeichert:\n{save_path}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"{e}")