import os, sys

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis
import os.path

from .resources import *

from .dialog.settings_dialog import SettingsDialog
from .dialog.plans_dialog import PlansDialog
from .dialog.orders_dialog import OrdersDialog
from .dialog.upload_dialog import UploadDialog
from .dialog.layer_details_dialog import LayerDetailsDock
from .utils.cognito_auth import CognitoSession

class xplanung24:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        self.cognito = CognitoSession()

        locale = (QSettings().value('locale/userLocale') or '')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'xplanung24_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&XPlanung24 Connector')
        self.first_start = None

        settings = QSettings()
        self.api_username = settings.value("xplanung24/api_username", "")
        self.api_password = settings.value("xplanung24/api_password", "")

    def tr(self, message):
        return QCoreApplication.translate('xplanung24', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):


        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        self.toolbar = self.iface.addToolBar("XPlanung24")
        self.toolbar.setObjectName("XPlanung24")

        preferences_icon_path = ':/plugins/xplanung24/assets/a2.png'
        plans_icon_path = ':/plugins/xplanung24/assets/a3.png'
        orders_icon_path = ':/plugins/xplanung24/assets/a4.png'
        upload_icon_path = ':/plugins/xplanung24/assets/a5.png' 
        get_layer_details_path = ':/plugins/xplanung24/assets/a1.png'

        self.add_action(
            upload_icon_path,
            text=self.tr(u'XPlan GML laden'),
            callback=self.show_upload_dialog,
            parent=self.iface.mainWindow())

        self.add_action(
            plans_icon_path,
            text=self.tr(u'Meine Pläne'),
            callback=self.show_plans_dialog,
            parent=self.iface.mainWindow())
        
        # self.add_action(
        #     orders_icon_path,
        #     text=self.tr(u'Aufträge anzeigen'),
        #     callback=self.show_orders_dialog,
        #     parent=self.iface.mainWindow())

        self.add_action(
            get_layer_details_path,
            text=self.tr(u'Ebenen Details anzeigen'),
            callback=self.show_layer_details_dialog,
            parent=self.iface.mainWindow()
        )

        self.add_action(
            preferences_icon_path,
            text=self.tr(u'Aktivierung'),
            callback=self.show_settings_dialog,
            parent=self.iface.mainWindow()
        )

        self.first_start = True


    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&XPlanung24 Connector'),
                action)
            self.iface.removeToolBarIcon(action)
    
    def ensure_authenticated(self) -> bool:
        if self.cognito.is_authenticated():
            return True

        if self.api_username and self.api_password:
            try:
                self.cognito.login(self.api_username, self.api_password)
                return True
            except Exception:
                pass

        dlg = SettingsDialog(self.iface.mainWindow(), username=self.api_username, password=self.api_password)
        if dlg.exec_():
            self.api_username, self.api_password = dlg.get_credentials()
            settings = QSettings()
            settings.setValue("xplanung24/api_username", self.api_username)
            settings.setValue("xplanung24/api_password", self.api_password)
            try:
                self.cognito.login(self.api_username, self.api_password)
                return True
            except Exception as e:
                self.iface.messageBar().pushMessage("Login-Fehler", str(e), level=Qgis.Critical, duration=5)
                return False
        else:
            return False


    def show_settings_dialog(self):
        username = self.api_username
        password = self.api_password

        dlg = SettingsDialog(self.iface.mainWindow(), username=username, password=password)
        if dlg.exec_():
            self.api_username, self.api_password = dlg.get_credentials()
            settings = QSettings()
            settings.setValue("xplanung24/api_username", self.api_username)
            settings.setValue("xplanung24/api_password", self.api_password)

            self.iface.messageBar().pushMessage(
                "Login", "Credentials gespeichert.", level=Qgis.Info, duration=3
            )

            try:
                self.cognito.login(self.api_username, self.api_password)
                self.iface.messageBar().pushMessage(
                    "Login", "Cognito Login erfolgreich.", level=Qgis.Info, duration=3
                )
            except Exception as e:
                self.iface.messageBar().pushMessage(
                    "Login-Fehler", str(e), level=Qgis.Critical, duration=5
                )

    def show_plans_dialog(self):
        if not self.ensure_authenticated():
            return

        dlg = PlansDialog(
            self.iface.mainWindow(),
            cognito_session=self.cognito,
        )
        dlg.exec_()

    def show_upload_dialog(self):
        """Zeigt den Upload-Dialog"""
        if not self.ensure_authenticated():
            return

        dlg = UploadDialog(
            self.iface.mainWindow(),
            cognito_session=self.cognito,
        )
        dlg.exec_()

    def show_orders_dialog(self):
        if not self.ensure_authenticated():
            return

        dlg = OrdersDialog(
            self.iface.mainWindow(),
            cognito_session=self.cognito,
        )
        dlg.exec_()

    def show_layer_details_dialog(self):
        if not self.ensure_authenticated():
            return

        if hasattr(self, "layer_details_dock") and self.layer_details_dock is not None:
            try:
                if self.layer_details_dock.isVisible():
                    self.iface.messageBar().pushMessage(
                        "XPlanung24", 
                        "Ebenen-Details ist bereits geöffnet.", 
                        level=Qgis.Info, 
                        duration=2
                    )
                    self.iface.addDockWidget(Qt.RightDockWidgetArea, self.layer_details_dock)
                    self.layer_details_dock.raise_()
                    return
            except RuntimeError:
                # Dock wurde gelöscht
                self.layer_details_dock = None

        # Neues Dock erstellen
        self.layer_details_dock = LayerDetailsDock(
            iface=self.iface,
            cognito_session=self.cognito,
        )
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.layer_details_dock)
        self.layer_details_dock.show()