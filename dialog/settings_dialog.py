from qgis.PyQt import QtCore, QtWidgets
from qgis.PyQt.QtGui import QIcon
import os


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, username="", password=""):
        super().__init__(parent)

        # === MAIN LAYOUT ===
        self.layout = QtWidgets.QVBoxLayout(self)

        # === ICON & WINDOW ===
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png")
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"⚠️ Icon not found at {icon_path}")

        self.setWindowTitle(" ")
        self.resize(400, 300)

        # === STYLES ===
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

            QPushButton {
                cursor:pointer; 
                border: 1px solid #000; 
                padding:6px 12px; 
                margin:2px; 
                border-radius:3px;
            }
            QPushButton:hover {
                background-color: #000;
                color: white;
                border: 1px solid #000;
            }
            QPushButton:pressed {
                background-color: #333;
                color: white;
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

        description_label = QtWidgets.QLabel("Plugin aktivieren")
        description_label.setStyleSheet("font-size: 14px; color: #000; font-weight: bold;")
        description_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        description_label1 = QtWidgets.QLabel(
            "Um das Plugin und alle Funktionen nutzen zu können, melden Sie sich bitte mit Ihren XPlanung24-Zugangsdaten an."
            "Falls Sie noch keinen Account besitzen, können Sie sich kostenlos registrieren – der Link dazu befindet sich weiter unten."
        )
        description_label1.setWordWrap(True)
        description_label1.setStyleSheet("font-size: 12px; color: #666; margin: 8px 0; font-weight: normal;")
        description_label1.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        text_layout.addWidget(description_label)
        text_layout.addWidget(description_label1)

        header_layout.addWidget(text_container, stretch=1)
        header_layout.addStretch()
        self.layout.addLayout(header_layout)

        # === LOGIN SECTION ===
        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setText(username)
        self.username_edit.setPlaceholderText("Benutzername")

        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setText(password)
        self.password_edit.setPlaceholderText("Passwort")
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        pass_layout = QtWidgets.QHBoxLayout()
        pass_layout.addWidget(self.password_edit)

        login_layout = QtWidgets.QFormLayout()
        login_layout.addRow("Benutzername:", self.username_edit)
        login_layout.addRow("Passwort:", pass_layout)

        login_group = QtWidgets.QGroupBox("Anmelden")
        login_group.setLayout(login_layout)

        # === REGISTRATION INFO ===
        self.future_settings_area = QtWidgets.QGroupBox("Noch keinen Account?")
        placeholder_label = QtWidgets.QLabel(
            'Registrieren Sie sich kostenlos auf '
            '<a href="https://app.xplanung24.de/">xplanung24.de</a>, '
            'um alle Funktionen nutzen zu können.'
        )
        placeholder_label.setOpenExternalLinks(True)
        future_layout = QtWidgets.QVBoxLayout()
        future_layout.addWidget(placeholder_label)
        self.future_settings_area.setLayout(future_layout)

        # === BUTTONS ===
        self.ok_button = QtWidgets.QPushButton("Verinden")
        self.ok_button.setStyleSheet("""
            QPushButton {
                padding: 8px 24px; background-color: #000; color: white; border: 1px solid #000;
            }
            QPushButton:hover { background-color: #333; border: 1px solid #333; color: white; }
            QPushButton:disabled { background-color: #eee; color: #666; border: 1px solid #ccc; }
        """)
        self.cancel_button = QtWidgets.QPushButton("Abbrechen")

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.ok_button)
        
        # === ADD WIDGETS TO MAIN LAYOUT ===
        self.layout.addWidget(login_group)

        self.layout.addStretch()
        self.layout.addLayout(button_layout)
        self.layout.addWidget(self.future_settings_area)
        # === CONNECT SIGNALS ===
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def toggle_password_visibility(self, checked):
        """Toggle password field visibility."""
        self.password_edit.setEchoMode(
            QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password
        )

    def get_credentials(self):
        """Return username and password."""
        return self.username_edit.text(), self.password_edit.text()
