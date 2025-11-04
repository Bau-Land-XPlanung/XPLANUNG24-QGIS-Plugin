from PyQt5 import QtWidgets, QtGui, QtCore
from .api import APIGetOrderTasks

TYPE_COLOR = {
    "error":    ("Fehler",      "#e11d48"),  # rot
    "question": ("Frage",       "#2563eb"),  # blau
    "reminder": ("Erinnerung",  "#f97316"),  # orange
    "request":  ("Korrektur",   "#16a34a"),  # grün
    "additional":("Änderung",   "#111827"),  # grau
}


class TasksReview(QtWidgets.QWidget):
    """PyQt Version der React-Komponente Tasksreview"""
    def __init__(self, order_id: str, company_id: str,
                 user_status: str, order_stage: str,
                 selected_version_status: str,
                 parent=None, cognito_session=None):
        super().__init__(parent)

        self.cognito_session = cognito_session
        self.order_id = order_id
        self.company_id = company_id
        self.user_status = user_status
        self.order_stage = order_stage
        self.selected_version_status = selected_version_status

        self.layout = QtWidgets.QVBoxLayout(self)
        self.review_items = []  # speichert die geladenen Items

        # Bereich für Listeneinträge
        self.list_container = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.list_container)

        # Button "Eintrag erfassen" (nur sichtbar wenn erlaubt)
        self.add_btn = QtWidgets.QPushButton("＋ Eintrag erfassen")
        self.add_btn.setVisible(
            self.user_status == "orderOwner"
            and self.order_stage == "inReview"
            and self.selected_version_status == "active"
        )
        self.add_btn.clicked.connect(self.open_create_dialog)
        self.layout.addWidget(self.add_btn, alignment=QtCore.Qt.AlignLeft)

        self.load_tasks()

    def load_tasks(self):
        if not (self.cognito_session and self.cognito_session.access_token):
            QtWidgets.QMessageBox.critical(self, "Fehler", "Keine gültige Authentifizierung vorhanden.")
            return
        """Tasks aus Backend holen und anzeigen."""
        try:
            self.review_items = APIGetOrderTasks(
                self.cognito_session, 
                order_id=self.order_id,
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Fehler", f"Konnte Review-Tasks nicht laden:\n{e}")
            self.review_items = []

        self.render_list()

    def render_list(self):
        # Vorherige Widgets entfernen
        while self.list_container.count():
            item = self.list_container.takeAt(0)
            if w := item.widget():
                w.deleteLater()

        if not self.review_items or self.selected_version_status != "active":
            self.list_container.addWidget(QtWidgets.QLabel("Keine Einträge vorhanden"))
            return

        for review in self.review_items:
            widget = self.build_review_widget(review)
            self.list_container.addWidget(widget)

    def build_review_widget(self, review: dict) -> QtWidgets.QWidget:
        """Erzeugt die Zeile für einen einzelnen Review-Eintrag."""
        row = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)

        # Icon: Kreis oder Check
        icon_label = QtWidgets.QLabel()
        if review.get("status") == "done":
            icon = "✔️"
        else:
            icon = "⭕"
        icon_label.setText(icon)
        h.addWidget(icon_label)

        # Type-Tag
        type_key = review.get("type")
        if type_key in TYPE_COLOR:
            type_name, color = TYPE_COLOR[type_key]
            type_label = QtWidgets.QLabel(type_name)
            type_label.setStyleSheet(
                f"border:1px solid {color}; color:{color}; "
                "border-radius:4px; padding:1px 4px; font-size:11px;"
            )
            h.addWidget(type_label)

        # Name
        name_label = QtWidgets.QLabel(review.get("name",""))
        if review.get("status") == "done":
            name_label.setStyleSheet("text-decoration: line-through; color: grey;")
        h.addWidget(name_label, stretch=1)

        # Klickbar: Details öffnen
        row.mouseReleaseEvent = lambda e, r=review: self.open_details(r)

        return row

    # --- Slots ---
    def open_details(self, review: dict):
        """Detaildialog öffnen – hier nur Beispiel."""
        dlg = ReviewDetailsDialog(review, self)   # musst du selbst implementieren
        dlg.exec_()

    def open_create_dialog(self):
        """Dialog für neuen Eintrag öffnen."""
        dlg = ReviewCreateDialog(self.order_id, self.company_id, self)
        if dlg.exec_():
            self.load_reviews()
