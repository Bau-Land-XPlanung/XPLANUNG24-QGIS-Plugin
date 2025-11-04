from qgis.PyQt import QtWidgets, QtCore
from datetime import datetime
from ..utils.task_list import TasksReview
from ..utils.api import APIGetOrderDetails
from ..utils.document_list import DocumentList
from ..utils.messaging_widget import MessagingWidget


class OrderDetailDialog(QtWidgets.QDialog):
    STATUS_MAP = {
        "draft": "Entwurf",
        "inTender": "In Ausschreibung",
        "contracted": "Beauftragt",
        "inDevelopment": "In Bearbeitung",
        "inReview": "Zur Abnahme",
        "completed": "Abgeschlossen"
    }

    def __init__(self, parent=None, cognito_session=None, order_id=None, plan_id=None):
        super().__init__(parent)
        self.cognito_session = cognito_session
        self.order_id = order_id
        self.plan_id = plan_id
        self.order = {}

        self.setWindowTitle(f"Auftrag: {plan_id or order_id}")
        self.resize(800, 500)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.detail_labels = {}

        for label_text in ["Auftragsnummer", "Auftragsbezeichnung", "Gemeinde", "Erstellt am", "Fortschritt"]:
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(f"<b>{label_text}:</b>"))
            value_label = QtWidgets.QLabel("-")
            row.addWidget(value_label)
            self.layout.addLayout(row)
            self.detail_labels[label_text] = value_label

        self.dynamic_area = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.dynamic_area)

        btn_layout = QtWidgets.QHBoxLayout()
        self.accept_button = QtWidgets.QPushButton("Auftrag abnehmen")
        self.accept_button.clicked.connect(self.accept_order)
        btn_layout.addWidget(self.accept_button)

        self.close_button = QtWidgets.QPushButton("Schließen")
        self.close_button.clicked.connect(self.close)
        btn_layout.addWidget(self.close_button)
        self.layout.addLayout(btn_layout)

        self.load_order_details()

    # -------------------------------------------------------------

    def load_order_details(self):
        if not (self.cognito_session and self.cognito_session.access_token):
            QtWidgets.QMessageBox.critical(self, "Fehler", "Keine gültige Authentifizierung vorhanden.")
            return

        try:
            self.order = APIGetOrderDetails(self.cognito_session, self.order_id)

            stage = self.order.get("stage", "-")
            self.detail_labels["Auftragsnummer"].setText(self.order.get("planId", "-"))
            self.detail_labels["Auftragsbezeichnung"].setText(
                (self.order.get("planDetails") or {}).get("name", "-")
            )
            self.detail_labels["Gemeinde"].setText(
                ((self.order.get("planDetails") or {}).get("community") or {}).get("name", "-")
            )
            created_at = self._format_timestamp(self.order.get("createdAt"))
            self.detail_labels["Erstellt am"].setText(created_at)
            self.detail_labels["Fortschritt"].setText(self.STATUS_MAP.get(stage, stage))

            # Review-Details laden
            reviews = self.order.get("reviewDetails", [])
            # sortiere absteigend nach Version wie im JS
            reviews = sorted(reviews, key=lambda x: int(x.get("version", 0)), reverse=True)
            self._build_dynamic_area(stage, reviews)

        except Exception as e:
            return

    # -------------------------------------------------------------

    def _build_dynamic_area(self, stage: str, reviewDetails: list):
        # alte Widgets entfernen
        while self.dynamic_area.count():
            item = self.dynamic_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Überschrift
        self.dynamic_area.addWidget(QtWidgets.QLabel("<b>Auftragsabnahme</b>"))

        # Scrollbereich erzeugen
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)  # horizontale Scrollbar deaktiviert
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

        for idx, review in enumerate(reviewDetails):
            box = QtWidgets.QGroupBox(f"Version {review.get('version', '-')}")
            box.setCheckable(False)
            box.setChecked(False)

            # --- Container-Widget für den Inhalt ---
            inner_widget = QtWidgets.QWidget()
            inner = QtWidgets.QVBoxLayout(inner_widget)

            status = review.get("status", "")
            created = self._format_timestamp(review.get("creationDate"))

            # Statusbeschreibung + Hintergrundfarbe bestimmen
            if status == "active" and stage == "inReview":
                inner.addWidget(QtWidgets.QLabel("Die Bearbeitung Ihres Auftrags wurde abgeschlossen und kann durch Sie geprüft werden."))
                inner_widget.setStyleSheet("background-color: #f3f4f6;")  # neutral
            elif status == "rejected":
                inner.addWidget(QtWidgets.QLabel("Diese Abnahme wurde bereits abgelehnt."))
                inner_widget.setStyleSheet("background-color: #ffcccc;")  # rot
            elif status == "cancel":
                inner.addWidget(QtWidgets.QLabel("Diese Abnahme wurde durch den Auftragnehmer zurückgezogen."))
                inner_widget.setStyleSheet("background-color: #ffffcc;")  # gelb
            elif idx == 0:
                inner.addWidget(QtWidgets.QLabel("Diese Abnahme wurde abgenommen."))
                inner_widget.setStyleSheet("background-color: #ccffcc;")  # grün
            else:
                inner.addWidget(QtWidgets.QLabel("Diese Abnahme ist abgelehnt oder zurückgezogen."))
                inner_widget.setStyleSheet("background-color: #ffffcc;")  # gelb

            inner.addWidget(QtWidgets.QLabel(f"Erstellt am: {created}"))

            # --- Dokumenten-Liste ---
            doc_list = DocumentList(self.cognito_session, self.order_id, review.get("reviewId", ""), self)
            inner.addWidget(doc_list)

            # --- Task-Liste ---
            tasks_widget = TasksReview(
                order_id=self.order_id,
                company_id=self.order.get("companyId", ""),
                user_status=self.order.get("userStatus", ""),
                order_stage=stage,
                selected_version_status=review.get("status", ""),
                cognito_session=self.cognito_session
            )
            inner.addWidget(tasks_widget)

            # Buttons wie gehabt …
            if status == "active" and stage not in ["inDevelopment", "completed"]:
                btn_row = QtWidgets.QHBoxLayout()
                reject_btn = QtWidgets.QPushButton("Ablehnen")
                reject_btn.clicked.connect(lambda _, rid=review.get("reviewId"): self.reject_review(rid))
                accept_btn = QtWidgets.QPushButton("Auftrag abnehmen")
                accept_btn.clicked.connect(lambda _, rid=review.get("reviewId"): self.complete_review(rid))
                btn_row.addWidget(reject_btn)
                btn_row.addWidget(accept_btn)
                inner.addLayout(btn_row)

            # --- Inner-Widget in die GroupBox einsetzen ---
            outer_layout = QtWidgets.QVBoxLayout()
            outer_layout.addWidget(inner_widget)
            box.setLayout(outer_layout)

            scroll_layout.addWidget(box)

        scroll_layout.addStretch()
        scroll_content.setLayout(scroll_layout)
        scroll.setWidget(scroll_content)

        self.dynamic_area.addWidget(scroll)

        if stage in ["contracted", "inDevelopment", "inReview", "completed"]:
            messaging = MessagingWidget(
                cognito_session=self.cognito_session,
                order_id=self.order_id,
                link_id=None,
                link_type="all",
                company_id=self.order.get("companyId", ""),
                stage=stage
            )
            self.dynamic_area.addWidget(messaging)

    def _format_timestamp(self, ts):
        if not ts or ts == "-":
            return "-"
        try:
            dt = datetime.fromtimestamp(int(ts) / 1000)
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return str(ts)

    # --- Platzhalter-APIs ----------------------------------------

    def reject_review(self, review_id):
        # TODO: Cognito API-Call (APIRejectReview)
        QtWidgets.QMessageBox.information(self, "Abgelehnt", f"Review {review_id} wurde abgelehnt.")
        self.load_order_details()

    def complete_review(self, review_id):
        # TODO: Cognito API-Calls (S3CopyPlanFromOrder, APICreateMultiplePlans,
        #       APIPostOrderLinkedMessaging, APISetOrderStage)
        QtWidgets.QMessageBox.information(self, "Abgenommen", f"Review {review_id} wurde abgenommen.")
        self.load_order_details()

    def accept_order(self):
        pass
