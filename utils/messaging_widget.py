from PyQt5 import QtWidgets, QtCore
import requests
from datetime import datetime
from .api import APIGetOrderAllMessaging, APIGetOrderLinkedMessaging, APIPostOrderLinkedMessaging


class ChatMessageWidget(QtWidgets.QWidget):
    """Einzelne Chatnachricht"""
    def __init__(self, activity_item: dict, current_company_id: str, parent=None):
        super().__init__(parent)
        self.activity_item = activity_item
        self.current_company_id = current_company_id
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        created = self._format_datetime(self.activity_item.get("createdAt"))
        msg = self.activity_item.get("message", "")
        username = self.activity_item.get("username", "-")
        company = self.activity_item.get("companyname", "-")

        # Spezialfälle
        link_type = self.activity_item.get("linkType")
        if link_type in ["progressUpdate", "progressUpdateStageBack"]:
            box = QtWidgets.QTextEdit(f"Update {created}\n{msg}")
            box.setReadOnly(True)
            box.setStyleSheet("background-color: #e5e7eb; color: #374151;")
            layout.addWidget(box)
            return
        elif link_type == "progressUpdateCompleted":
            box = QtWidgets.QTextEdit(f"Auftrag abgeschlossen {created}\n{msg}")
            box.setReadOnly(True)
            box.setStyleSheet("background-color: #d1d5db; color: #111827; font-weight: bold;")
            layout.addWidget(box)
            return

        # Normale Nachrichten
        container = QtWidgets.QWidget()
        inner = QtWidgets.QVBoxLayout(container)
        inner.setContentsMargins(10, 5, 10, 5)

        meta = QtWidgets.QLabel(f"{username} ({company}) – {created}")
        meta.setStyleSheet("font-size: 11px; color: gray;")

        text = QtWidgets.QLabel(msg)
        text.setWordWrap(True)

        inner.addWidget(meta)
        inner.addWidget(text)

        if self.activity_item.get("createdByCompany") == self.current_company_id:
            # Rechts ausrichten
            inner.setAlignment(meta, QtCore.Qt.AlignRight)
            inner.setAlignment(text, QtCore.Qt.AlignRight)
            container.setStyleSheet("background-color: #f3f4f6")
        else:
            # Links ausrichten
            inner.setAlignment(meta, QtCore.Qt.AlignLeft)
            inner.setAlignment(text, QtCore.Qt.AlignLeft)
            container.setStyleSheet("background-color: #ffffff")

        layout.addWidget(container)

    def _format_datetime(self, dt_str):
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            return dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            return dt_str


class MessageInputWidget(QtWidgets.QWidget):
    """Eingabefeld für neue Nachrichten"""
    sendMessage = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.setFixedHeight(60)

        send_btn = QtWidgets.QPushButton("Senden")
        send_btn.clicked.connect(self._on_send)

        layout.addWidget(self.text_edit)
        layout.addWidget(send_btn)

    def _on_send(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            self.sendMessage.emit(text)
            self.text_edit.clear()


class MessagingWidget(QtWidgets.QWidget):
    """Haupt-Nachrichtenbereich"""
    def __init__(self, cognito_session, order_id, link_id=None, link_type=None,
                 company_id=None, stage=None, parent=None):
        super().__init__(parent)
        self.cognito_session = cognito_session
        self.order_id = order_id
        self.link_id = link_id
        self.link_type = link_type
        self.company_id = company_id
        self.stage = stage
        self.activities = []

        self._build_ui()
        self._load_messages()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("🔔 Nachrichtenbereich")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Scrollbereich für Nachrichten
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.messages_container = QtWidgets.QWidget()
        self.messages_layout = QtWidgets.QVBoxLayout(self.messages_container)
        self.messages_layout.addStretch()
        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area)

        # Eingabefeld nur, wenn Auftrag nicht abgeschlossen
        if self.stage != "completed":
            self.message_input = MessageInputWidget()
            self.message_input.sendMessage.connect(self._save_message)
            layout.addWidget(self.message_input)

    def _load_messages(self):
        try:
            if self.link_type == "all":
                fetched = APIGetOrderAllMessaging(self.cognito_session, self.order_id)
            else:
                fetched = APIGetOrderLinkedMessaging(
                    self.cognito_session,
                    self.order_id,
                    self.link_id,
                    self.link_type
                )
            self.activities = fetched or []
            self._render_messages()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"Nachrichten konnten nicht geladen werden:\n{e}")

    def _render_messages(self):
        # Alte Widgets (außer Stretch) löschen
        for i in reversed(range(self.messages_layout.count())):
            item = self.messages_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        # Nachrichten in chronologischer Reihenfolge einfügen
        for activity in self.activities:
            msg_widget = ChatMessageWidget(activity, self.company_id)
            self.messages_layout.addWidget(msg_widget)

        # Stretch immer am Ende
        self.messages_layout.addStretch()

        # Automatisch nach unten scrollen
        QtCore.QTimer.singleShot(0, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def _save_message(self, text):
        try:
            message_data = {
                "ordersId": self.order_id,
                "linkId": self.link_id,
                "linkType": self.link_type,
                "message": text,
            }
            response = APIPostOrderLinkedMessaging(self.cognito_session, message_data, company_id=self.company_id)
            if response:
                self.activities.insert(0, response)
                self._render_messages()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Fehler", f"Nachricht konnte nicht gesendet werden:\n{e}")
