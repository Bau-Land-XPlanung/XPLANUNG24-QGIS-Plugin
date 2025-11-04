# styles.py
import os
from qgis.core import (
    QgsVectorLayer,
    QgsProject,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsRasterMarkerSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsRenderContext,
    QgsWkbTypes
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt
from pprint import pprint
from .layer import (
    _get_border,
    _get_base_background,
    _get_background_pattern,
    _get_icon
)

LINE_WIDTH_FACTOR = 1  # globale Skalierung für Linienbreiten

def _find_server_styles_for_layer(vlayer, server_styles):
    """Findet ALLE passenden Server-Styles für einen Layer (kann mehrere sein!)"""
    if not server_styles:
        return []
    
    layer_ids = set()
    try:
        # Sammle ALLE Features, nicht nur die ersten 200!
        for f in vlayer.getFeatures():  # KEIN LIMIT mehr!
            # common field names: try several possibilities
            for possible in ("gml_id", "gmlid", "gmlId", "id", "ID", "fid", "gml_identifier"):
                idx = f.fields().indexFromName(possible)
                if idx != -1:
                    val = f[possible]
                    if val is not None:
                        layer_ids.add(str(val).strip())
                        break  # Gehe zum nächsten Feature sobald wir eine ID haben
            # also add feature id as string (fallback)
            layer_ids.add(str(f.id()))
    except Exception as e:
        print(f"  ⚠️ Fehler beim Sammeln der Layer-IDs: {e}")
    
    # also include layer name itself
    layer_ids.add(vlayer.name())
    
    # Sammle ALLE passenden Styles
    matching_styles = []
    for style_entry in server_styles:
        ids = style_entry.get("i") or []
        ids = {str(x).strip() for x in ids if x is not None}
        
        matched_ids = layer_ids & ids
        
        if matched_ids:
            matching_styles.append({
                "style": style_entry.get("v"),
                "name": style_entry.get("n", None),
                "n_value": style_entry.get("n", None),
                "ids": list(matched_ids)
            })
               
    return matching_styles

def apply_style_to_gml_layers(gml_path: str, default_name: str = "Layer", server_styles: list = None):
    tmp_layer = QgsVectorLayer(gml_path, default_name, "ogr")
    sublayers = tmp_layer.dataProvider().subLayers()
    if not sublayers:
        print("⚠️ Keine Sublayer in GML gefunden.")
        return []

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group_name = os.path.splitext(os.path.basename(gml_path))[0] or default_name
    plan_group = root.addGroup(default_name or group_name)
    
    # ✅ WICHTIG: Sammle ALLE Memory-Layer aus ALLEN Sublayers BEVOR wir sie hinzufügen
    all_mem_layers_with_priority = []

    for sub_info in sublayers:
        name = sub_info.split("!!::!!")[1]
        print(f"\n📄 Lade Sublayer {name}")
        uri = f"{gml_path}|layername={name}"
        vlayer = QgsVectorLayer(uri, name, "ogr")
        if not vlayer.isValid():
            print(f"  ⚠️ Layer {name} ist ungültig – wird übersprungen.")
            continue

        # --- Split by geometry type ---
        geom_groups = {}
        for feat in vlayer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue

            # Get full WKB type (e.g., MultiPolygon, LineString, etc.)
            wkb_type = geom.wkbType()

            # Get readable base geometry type (e.g., "Point", "Line", "Polygon")
            base_type = QgsWkbTypes.geometryType(wkb_type)
            gtype = QgsWkbTypes.geometryDisplayString(base_type)

            geom_groups.setdefault(gtype, []).append(feat)

        # --- Create memory layers with priority tracking ---
        for gtype, feats in geom_groups.items():
            first_geom = feats[0].geometry()
            wkb_type = first_geom.wkbType()

            # ✅ Correct: pass WKB type (not GeometryType) to displayString
            wkb_name = QgsWkbTypes.displayString(wkb_type)

            mem_layer = QgsVectorLayer(f"{wkb_name}?crs={vlayer.crs().authid()}",
                                       f"{name} ({gtype})", "memory")
            mem_layer_data = mem_layer.dataProvider()
            mem_layer_data.addAttributes(vlayer.fields())
            mem_layer.updateFields()
            mem_layer_data.addFeatures(feats)

            print(f"   ➕ {len(feats)} Features → {name} ({gtype})")

            # --- Find matching styles and determine priority ---
            matching_styles = _find_server_styles_for_layer(mem_layer, server_styles)
            
            # Bestimme die Priorität (niedrigster n_value = unten im Stack)
            if matching_styles:
                min_n_value = min([s.get("n_value") or 0 for s in matching_styles])
            else:
                min_n_value = 9999  # Layers ohne Style ganz oben
            
            # ✅ Sammle in der GLOBALEN Liste
            all_mem_layers_with_priority.append({
                'layer': mem_layer,
                'styles': matching_styles,
                'priority': min_n_value,
                'gtype': gtype,
                'sublayer_name': name
            })

    # ✅ JETZT ERST: Sortiere ALLE Layer aus ALLEN Sublayers nach Priority
    # HÖCHSTE n_value zuerst, da QGIS von oben einfügt
    all_mem_layers_with_priority.sort(key=lambda x: x['priority'], reverse=True)
    
    print(f"\n🔢 GLOBALE Layer-Reihenfolge nach n_value (höchste zuerst → wird oben liegen):")
    for item in all_mem_layers_with_priority:
        print(f"   {item['layer'].name()} → Priority: {item['priority']}")

    # ✅ JETZT ERST: Layer zum Projekt hinzufügen und Styles anwenden
    all_layers = []
    for item in all_mem_layers_with_priority:
        mem_layer = item['layer']
        matching_styles = item['styles']
        
        # Styles innerhalb des Layers auch nach n_value sortieren
        if matching_styles:
            matching_styles.sort(key=lambda x: x.get("n_value") or 0)
            print(f"   🎨 Wende {len(matching_styles)} Styles an für {mem_layer.name()}")
            
            for match in matching_styles:
                _apply_server_style_safe(mem_layer, match["style"], match["ids"])
        else:
            _apply_default_safe(mem_layer)

        project.addMapLayer(mem_layer, False)
        plan_group.addLayer(mem_layer)
        all_layers.append(mem_layer)

    print(f"\n✅ {len(all_layers)} Layer erstellt und nach n_value sortiert.")
    return all_layers

def _apply_server_style_safe(vlayer, style_dict, ids):
    geom_type = vlayer.geometryType()

    base_border = style_dict.get("baseBorder") or None
    base_bg = style_dict.get("baseBackground") or None
    basesIcon = style_dict.get("basesIcon") or None
    base_bg_pattern = style_dict.get("baseBackgroundPattern") or None
    base_text = style_dict.get("basesText") or None
    overlay_border = style_dict.get("overlayBorder") or None
    overlay_icon = style_dict.get("overlayIcon") or None

    # POLYGON
    if geom_type == 2:
        existing_renderer = vlayer.renderer()
        if isinstance(existing_renderer, QgsRuleBasedRenderer):
            renderer = existing_renderer
            root_rule = renderer.rootRule()
        else:
            root_rule = QgsRuleBasedRenderer.Rule(None)
            renderer = QgsRuleBasedRenderer(root_rule)
            vlayer.setRenderer(renderer)

        fill_sym = QgsFillSymbol.createSimple({})
        fill_sym.deleteSymbolLayer(0)

        if isinstance(base_border, dict):
            outline_layer = _get_border(base_border, LINE_WIDTH_FACTOR)
            fill_sym.appendSymbolLayer(outline_layer)

        if isinstance(base_bg, dict):
            outline_layer, fill_layer, pattern_layer = _get_base_background(base_bg, LINE_WIDTH_FACTOR)

            for layer in [fill_layer, pattern_layer, outline_layer]:
                if layer is not None:
                    fill_sym.appendSymbolLayer(layer)

        if isinstance(base_bg_pattern, dict):
            pattern_layer = _get_background_pattern(base_bg_pattern, LINE_WIDTH_FACTOR)
            if pattern_layer is not None:
                fill_sym.appendSymbolLayer(pattern_layer)

        if isinstance(overlay_border, dict):
            outline_layer = _get_border(overlay_border, LINE_WIDTH_FACTOR)
            fill_sym.appendSymbolLayer(outline_layer)

        # Icon direkt im Fill-Symbol hinzufügen (für Polygon-Centroid)
        if isinstance(overlay_icon, dict):
            icon_layer = _get_icon(overlay_icon, LINE_WIDTH_FACTOR, geom_type=2)
            if icon_layer is not None:
                fill_sym.appendSymbolLayer(icon_layer)
        
        if isinstance(basesIcon, dict):
            icon_layer = _get_icon(basesIcon, LINE_WIDTH_FACTOR, geom_type=2)
            if icon_layer is not None:
                fill_sym.appendSymbolLayer(icon_layer)

        id_conditions = [f'"gml_id" = \'{gid}\'' for gid in ids]
        filter_exp = " OR ".join(id_conditions)
        rule = QgsRuleBasedRenderer.Rule(fill_sym, filterExp=filter_exp, label=f"Style")
        root_rule.appendChild(rule)

        vlayer.triggerRepaint()

    # LINE
    elif geom_type == 1:
        existing_renderer = vlayer.renderer()
        if isinstance(existing_renderer, QgsRuleBasedRenderer):
            renderer = existing_renderer
            root_rule = renderer.rootRule()
        else:
            root_rule = QgsRuleBasedRenderer.Rule(None)
            renderer = QgsRuleBasedRenderer(root_rule)
            vlayer.setRenderer(renderer)

        line_sym = QgsLineSymbol.createSimple({})
        line_sym.deleteSymbolLayer(0)

        if isinstance(base_border, dict):
            outline_layer = _get_border(base_border, LINE_WIDTH_FACTOR)
            line_sym.appendSymbolLayer(outline_layer)

        if isinstance(overlay_border, dict):
            outline_layer = _get_border(overlay_border, LINE_WIDTH_FACTOR)
            line_sym.appendSymbolLayer(outline_layer)

        # Icon direkt im Line-Symbol hinzufügen
        if isinstance(overlay_icon, dict):
            print(f"  🔷 Füge overlay_icon zu Polygon hinzu: {overlay_icon}")
            icon_layer = _get_icon(overlay_icon, LINE_WIDTH_FACTOR, geom_type=1)
            if icon_layer is not None:
                line_sym.appendSymbolLayer(icon_layer)

        if isinstance(basesIcon, dict):
            icon_layer = _get_icon(basesIcon, LINE_WIDTH_FACTOR, geom_type=1)
            if icon_layer is not None:
                line_sym.appendSymbolLayer(icon_layer)

        id_conditions = [f'"gml_id" = \'{gid}\'' for gid in ids]
        filter_exp = " OR ".join(id_conditions)
        rule = QgsRuleBasedRenderer.Rule(line_sym, filterExp=filter_exp, label=f"Style")
        root_rule.appendChild(rule)

        vlayer.triggerRepaint()

    elif geom_type == 0:
        existing_renderer = vlayer.renderer()
        if isinstance(existing_renderer, QgsRuleBasedRenderer):
            renderer = existing_renderer
            root_rule = renderer.rootRule()
        else:
            root_rule = QgsRuleBasedRenderer.Rule(None)
            renderer = QgsRuleBasedRenderer(root_rule)
            vlayer.setRenderer(renderer)

        icon_sym = QgsMarkerSymbol()
        icon_sym.deleteSymbolLayer(0)
        if isinstance(basesIcon, dict):
            icon_layer = _get_icon(basesIcon, LINE_WIDTH_FACTOR, geom_type=0)
            icon_sym.appendSymbolLayer(icon_layer)

        if isinstance(overlay_icon, dict):
            overlay_layer = _get_icon(overlay_icon, LINE_WIDTH_FACTOR, geom_type=0)
            icon_sym.appendSymbolLayer(overlay_layer)
        
        id_conditions = [f'"gml_id" = \'{gid}\'' for gid in ids]
        filter_exp = " OR ".join(id_conditions)
        rule = QgsRuleBasedRenderer.Rule(icon_sym, filterExp=filter_exp, label=f"Style")
        root_rule.appendChild(rule)

        vlayer.triggerRepaint()

def _apply_default_safe(vlayer):
    """Standard-Style wenn kein Server-Style vorhanden"""
    geom_type = vlayer.geometryType()
    if geom_type == 2:
        sym = QgsFillSymbol.createSimple({
            "color": "#e6e6e6",
            "outline_color": "#333333",
            "outline_width": str(LINE_WIDTH_FACTOR)
        })
    elif geom_type == 1:
        sym = QgsLineSymbol.createSimple({
            "color": "#333333",
            "width": str(LINE_WIDTH_FACTOR)
        })
    else:
        sym = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": "#333333",
            "size": str(3.0 * LINE_WIDTH_FACTOR)
        })

    vlayer.setRenderer(QgsSingleSymbolRenderer(sym))
    vlayer.triggerRepaint()