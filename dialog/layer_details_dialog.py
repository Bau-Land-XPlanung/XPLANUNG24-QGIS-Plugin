from qgis.PyQt.QtWidgets import QDockWidget, QVBoxLayout, QTextBrowser, QWidget
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.core import Qgis, QgsProject
from ..utils.identify_tool import IdentifyMapTool


class LayerDetailsDock(QDockWidget):
    def __init__(self, iface, cognito_session):
        super().__init__("XPlanung24 - Ebenen Details", iface.mainWindow())
        self.iface = iface
        self.cognito = cognito_session
        self.map_tool = None
        self.api_response = None
        
        self.setup_ui()
        self.setup_map_tool()
    
    def setup_ui(self):
        # Container Widget
        widget = QWidget()
        layout = QVBoxLayout()
        
        # === Styles ===
        self.setStyleSheet("""
            QWidget { background-color: #eee; padding:2px; border:0; }
            QTextBrowser { background-color: #fff; padding:12px; }
           
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
        
        # HTML/Text Browser für die Anzeige
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)  # Wichtig: Auf False setzen für interne Links!
        self.text_browser.anchorClicked.connect(self.on_anchor_clicked)
        self.text_browser.setHtml("""
            <h3>XPLAN Flächeninhalte anzeigen</h3>
            <p>
              Klicken Sie auf eine Fläche in Ihrem Plan, um alle zugehörigen XPlan-Informationen der Fläche anzuzeigen. 
              <br><br>
              <strong>Hinweis:</strong> XPLANUNG24 übernimmt automatisch die Übersetzung sämtlicher XPlan-Objekte, Codes und Bezeichnungen in ein lesbares, verständliches Format – damit Sie die Inhalte Ihres Plans einfach nachvollziehen können.
            </p>
        """)
        layout.addWidget(self.text_browser)
        
        widget.setLayout(layout)
        self.setWidget(widget)
    
    def setup_map_tool(self):
        """Richtet das Map-Tool für Feature-Identifikation ein"""
        self.map_tool = IdentifyMapTool(self.iface, radius=5)
        self.map_tool.featureIdentified.connect(self.handle_feature_identified)
        self.iface.mapCanvas().setMapTool(self.map_tool)
        
        self.iface.messageBar().pushMessage(
            "XPlanung24", 
            "Klicken Sie auf die Karte, um Ebenen-Details abzurufen.", 
            level=Qgis.Info, 
            duration=4
        )
    
    def handle_feature_identified(self, results):
        """Verarbeitet identifizierte Features und ruft die Details aus Layer Properties ab"""
        if not results:
            self.iface.messageBar().pushMessage(
                "XPlanung24",
                "Keine Features in der Nähe gefunden.",
                level=Qgis.Warning,
                duration=3,
            )
            return

        # Sammle alle GML-IDs und hole Details vom ANGEKLICKTEN Layer
        gml_ids = []
        details_data = None
        
        for layer_name_or_obj, gml_id in results:
            if gml_id:
                gml_ids.append(gml_id)
            
            layer = None
            if isinstance(layer_name_or_obj, str):
                for proj_layer in QgsProject.instance().mapLayers().values():
                    if proj_layer.name() == layer_name_or_obj:
                        layer = proj_layer
                        break
            else:
                layer = layer_name_or_obj
            
            # 🔑 Hole Details aus Layer Custom Property
            if layer is not None and details_data is None:
                try:
                    import json
                    details_json = layer.customProperty("xplanung24_details")
                    if details_json:
                        details_data = json.loads(details_json)
                        print(f"✓ {len(details_data)} Detail-Sections aus Layer geladen")
                except Exception as e:
                    print(f"⚠️ Fehler beim Laden der Details: {e}")
        
        if not gml_ids:
            self.iface.messageBar().pushMessage(
                "XPlanung24",
                "Keine gültigen GML-IDs gefunden.",
                level=Qgis.Warning,
                duration=3,
            )
            return
        
        if not details_data:
            self.iface.messageBar().pushMessage(
                "XPlanung24",
                "Keine Details für diesen Plan gefunden.",
                level=Qgis.Warning,
                duration=3,
            )
            return

        # 🔑 Filtere Details nach GML-IDs
        filtered_details = []
        for section in details_data:
            if isinstance(section, dict) and 'details' in section:
                # Filtere Details die zu unseren gmlIds gehören
                matching_details = []
                for detail_group in section.get('details', []):
                    if isinstance(detail_group, dict) and 'gmlId' in detail_group:
                        if detail_group['gmlId'] in gml_ids:
                            matching_details.append(detail_group.get('details', []))
                
                # Flatten und Section hinzufügen
                if matching_details:
                    flattened = []
                    for detail_list in matching_details:
                        if isinstance(detail_list, list):
                            flattened.extend(detail_list)
                    
                    if flattened:
                        filtered_details.append({
                            'name': section.get('name', 'Unbenannt'),
                            'details': flattened
                        })
        
        print(f"Gefilterte Details: {len(filtered_details)} Sections für {len(gml_ids)} GML-IDs")
        
        # Speichere gefilterte Response für Navigation
        self.api_response = filtered_details
        
        # Zeige Inhaltsverzeichnis
        self.show_table_of_contents()

        self.iface.messageBar().pushMessage(
            "XPlanung24",
            f"Details für {len(gml_ids)} Feature(s) geladen.",
            level=Qgis.Info,
            duration=4,
        )
    
    def show_table_of_contents(self):
        """Zeigt das Inhaltsverzeichnis aller Sections"""
        html = """
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #fafafa;
                padding: 10px 14px;
            }
 
            .title {
                padding-top:6px;
                padding-left:6px;
            }   
            
            .title h2{
                font-size:28px;
                font-weight:500;
            }
            
            .toc-block {
                margin-top:12px;
            }    
                 
            .toc-item {
                border-top:1px solid #eee;
                padding:12px;
            }       
            .toc-item a {
                padding:12px;
                font-size:16px;
                color:#000;
                text-decoration:none;
            }
        </style>
        """
        
        html += "<div class='title'>"
        html += "<h2>Ebene wählen</h2>"
        html += "</div>"
     
        if isinstance(self.api_response, list):
            html += "<table class='toc-block'>"    
            for idx, section in enumerate(self.api_response):
                if isinstance(section, dict) and 'name' in section:
                    section_name = section.get('name', 'Unbenannt')
                    detail_count = len(section.get('details', []))
                    html += "<tr style='margin:12px; width:100%;'>"
                    html += f"<td class='toc-item'><a href='section:{idx}' class='toc-link'>{section_name}</a></td>"
                    html += "</tr>"
            html += "</table>"           
        self.text_browser.setHtml(html)
    
    def show_section(self, section_idx):
        """Zeigt eine einzelne Section mit Details"""
        if not isinstance(self.api_response, list) or section_idx >= len(self.api_response):
            return
        
        section = self.api_response[section_idx]
        section_name = section.get('name', 'Unbenannt')
        
        html = """
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #fafafa;
                padding: 10px 14px;
            }
            h2 {
                color: #1a1a1a;
                font-size: 20px;
                margin-bottom: 15px;
                font-weight: bold;
            }
            .top-bar {
                display:block;
                padding: 4px 4px 8px 4px ;
            }
            
            .top-bar a{
                font-size:20px;
                color:#000;
                text-decoration:none;
            }
            
            .title {
                padding-top:6px;
                padding-left:6px;
            }   
            
            .title h2{
                font-size:28px;
                font-weight:500;
            }
            .detail-item {
                padding-top:18px;
                display:block;
                margin-top:18px;
            }
            
            .detail-value {
                font-size:12px;
                font-weight:200;
                color:#666;
            }
            
            .detail-name {
                font-size:12px;
                font-weight:500;
                color: #011627 !important;
                padding-top:6px
            }
            
            .detail-block {
                font-size:12px;
                font-weight:300;
                color:#666;
                padding-top:6px;
            }
            
            .detail-blockname {
                font-size:12px;
                margin-top:6px;
                font-weight:500;
                color: #666 !important;
                padding-right:12px;
                padding-bottom:4px;
                width:250px;
            }
            
            .detail-item {
                padding:6px;
                border-left:4px solid #eee;
            }
            .details-table {
                margin-top:12px;
            }
        </style>
        """

        html += "<table class='top-bar'>"
        html += "<tr>"
        html += "<td>"
        html += "<a href='toc' class='back-button'>←</a>"
        html += "</td>"
        html += "<td class='title'>"
        html += f"<h2>{section_name}</h2>"
        html += "</td>"
        html += "</tr>"
        html += "</table>"
        
        details = section.get('details', [])
        if details:
            old_name = ""
        
            for detail in details:
                if isinstance(detail, dict):
                    detail_name = detail.get('name', '')
                    detail_type = detail.get('type', '')
                    detail_values = detail.get('values', '')
                    
                    # Spezielle Behandlung für Text-Abschnitt
                    if detail_name == 'Text-Abschnitt' and detail_type == 'json' and isinstance(detail_values, list):
                        
                        if old_name != detail_name and detail_name == 'Text-Abschnitt': 
                            html += "<div class='detail-item'>"
                            html += "<div class='detail-name'>Text-Abschnitt:</div>"
                            html += "</div>"
                            old_name = detail_name

                        html += "<table class='details-table'>"
                        html += "<tr>"
                        html += "<td class='detail-item'>"
                        
                        for item in detail_values:
                            if isinstance(item, dict):
                                label = item.get('label', '')
                                value = item.get('value', '')
                                
                                if label and value:
                                    formatted_value = str(value).replace('\\r\\n', '<br>').replace('\r\n', '<br>').replace('\n', '<br>')
                                    html += f"<div class='detail-blockname'>{label}:</div>"
                                    html += f"<div class='detail-block'>{formatted_value}</div>"
                            elif isinstance(item, str):
                                try:
                                    import ast
                                    parsed = ast.literal_eval(item)
                                    if isinstance(parsed, dict):
                                        label = parsed.get('label', '')
                                        value = parsed.get('value', '')
                                        
                                        if label and value:
                                            formatted_value = str(value).replace('\\r\\n', '<br>').replace('\r\n', '<br>').replace('\n', '<br>')
                                            html += f"<div class='detail-blockname'>{label}:</div>"
                                            html += f"<div class='detail-block'>{formatted_value}</div>"
                                except:
                                    html += f"<div class='detail-value'>{item}</div>"
                        
                        html += "</td>"
                        html += "</tr>"
                        html += "</table>"
                    
                    else:
                        html += "<div class='detail-item'>"
                        html += f"<div class='detail-name'>{detail_name}:</div> "
                        
                        if detail_type == 'document' and isinstance(detail_values, list):
                            html += "<ul class='detail-item'>"
                            for doc in detail_values:
                                if isinstance(doc, dict):
                                    doc_name = doc.get('name', 'Dokument')
                                    doc_url = doc.get('url', '')
                                    if doc_url:
                                        html += f"<li>📄 <a href='{doc_url}' target='_blank'>{doc_name}</a></li>"
                                else:
                                    html += f"<li>{doc}</li>"
                            html += "</ul>"
                        
                        elif detail_type == 'json' and isinstance(detail_values, list):
                            html += "<ul style='color:#666'>"
                            for item in detail_values:
                                html += f"<li>{item}</li>"
                            html += "</ul>"
                        
                        elif isinstance(detail_values, list):
                            html += "<ul>"
                            for val in detail_values:
                                html += f"<li>{val}</li>"
                            html += "</ul>"
                        
                        elif isinstance(detail_values, str):
                            formatted_value = detail_values.replace('\n', '<br>')
                            html += f"<div class='detail-value'>{formatted_value}</div>"
                        
                        else:
                            html += f"<div class='detail-value'>{detail_values}</div>"
                        
                        html += "</div>"
        else:
            html += "<p><i>Keine Details verfügbar</i></p>"
        
        self.text_browser.setHtml(html)
    
    def on_anchor_clicked(self, url):
        """Handler für Link-Klicks"""
        url_str = url.toString()
        
        print(f"Link geklickt: {url_str}")  # Debug
        
        if url_str == 'toc':
            # Zurück zum Inhaltsverzeichnis
            self.show_table_of_contents()
        elif url_str.startswith('section:'):
            # Zeige Section
            try:
                section_idx = int(url_str.split(':')[1])
                self.show_section(section_idx)
            except Exception as e:
                print(f"Fehler beim Öffnen der Section: {e}")
        elif url_str.startswith('http://') or url_str.startswith('https://'):
            # Externe Links (z.B. Dokumente) im Browser öffnen
            from qgis.PyQt.QtGui import QDesktopServices
            QDesktopServices.openUrl(url)
    
    def closeEvent(self, event):
        """Stelle sicher, dass das Map-Tool deaktiviert wird beim Schließen"""
        if self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
        super().closeEvent(event)