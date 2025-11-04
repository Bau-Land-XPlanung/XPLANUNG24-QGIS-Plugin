from qgis.PyQt.QtWidgets import QDockWidget, QVBoxLayout, QWidget
from qgis.PyQt.QtWebKitWidgets import QWebView
from qgis.PyQt.QtCore import QUrl


class WebViewerDock(QDockWidget):
    def __init__(self, iface, url, title="Web Viewer"):
        super().__init__(title, iface.mainWindow())
        self.iface = iface
        
        # Widget und Layout
        widget = QWidget()
        layout = QVBoxLayout()
        
        # WebView
        self.web_view = QWebView()
        if url:
            self.web_view.setUrl(QUrl(url))
        
        layout.addWidget(self.web_view)
        widget.setLayout(layout)
        self.setWidget(widget)
