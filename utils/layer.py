from qgis.core import (
    QgsSimpleLineSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsRasterMarkerSymbolLayer,
    QgsMarkerLineSymbolLayer,
    QgsCentroidFillSymbolLayer,
    QgsMarkerSymbol,
    QgsUnitTypes
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt, QPointF

BASE_ICON_URL = "https://www.xplanung24.de/wp-content/uploads/icons/"

def _col(val, default):
    try:
        return QColor(val) if val else QColor(default)
    except Exception:
        return QColor(default)
 
def _get_border(border, LINE_WIDTH_FACTOR):
    border_col = _col(border.get("borderColor"), "#333333")
    border_opacity = border.get("borderOpacity", 1)
    border_dash = border.get("borderDashArray", None)
    border_size = border.get("borderSize", 1) * LINE_WIDTH_FACTOR
    border_offset = border.get("borderOffset", 0) * LINE_WIDTH_FACTOR

    border_col.setAlphaF(float(border_opacity))
    
    outline_layer = QgsSimpleLineSymbolLayer()
    outline_layer.setColor(border_col)
    outline_layer.setWidth(border_size)
    outline_layer.setPenStyle(Qt.DashLine if border_dash else Qt.SolidLine)
    outline_layer.setOffset(border_offset)
    
    # Einheit auf Pixel setzen
    outline_layer.setWidthUnit(QgsUnitTypes.RenderPixels)
    outline_layer.setOffsetUnit(QgsUnitTypes.RenderPixels)
    
    return outline_layer
 
def _get_base_background(base_bg, LINE_WIDTH_FACTOR):
    fill_color = _col(base_bg.get("backgroundColor"), None)
    fill_opacity = base_bg.get("backgroundOpacity", 1)
    fill_border_color = _col(base_bg.get("borderColor"), None)
    fill_border_opacity = base_bg.get("borderOpacity", 1)
    fill_border_size = base_bg.get("borderSize", 1) * LINE_WIDTH_FACTOR
    fill_border_offset = base_bg.get("borderOffset", 0) * LINE_WIDTH_FACTOR

    if fill_color is not None:
        fill_color.setAlphaF(float(fill_opacity))
    if fill_border_color is not None:
        fill_border_color.setAlphaF(float(fill_border_opacity))

    pattern_style = base_bg.get("backgroundPattern", None)
    pattern_line_color = _col(base_bg.get("patternColor"), "#333333")
    pattern_line_color.setAlphaF(float(fill_opacity))

    outline_layer = None
    if fill_border_color is not None:
        outline_layer = QgsSimpleLineSymbolLayer()
        outline_layer.setColor(fill_border_color)
        outline_layer.setWidth(fill_border_size)
        outline_layer.setPenStyle(Qt.SolidLine)
        outline_layer.setOffset(fill_border_offset)
        
        # Einheit auf Pixel setzen
        outline_layer.setWidthUnit(QgsUnitTypes.RenderPixels)
        outline_layer.setOffsetUnit(QgsUnitTypes.RenderPixels)

    fill_layer = None
    if fill_color is not None:
        fill_layer = QgsSimpleFillSymbolLayer()
        fill_layer.setColor(fill_color)

    pattern_layer = None
    if pattern_style is not None:
        pattern_layer = QgsSimpleFillSymbolLayer()
        pattern_layer.setBrushStyle(Qt.FDiagPattern)
        pattern_layer.setColor(pattern_line_color)

    return outline_layer, fill_layer, pattern_layer

def _get_background_pattern(base_bg_pattern, LINE_WIDTH_FACTOR):
    pattern_opacity = base_bg_pattern.get("backgroundOpacity", 1.0)
    pattern_style = base_bg_pattern.get("backgroundPattern", None)
    pattern_line_color = _col(base_bg_pattern.get("patternColor"), "#333333")

    pattern_line_color.setAlphaF(float(pattern_opacity))

    pattern_layer = None
    if pattern_style is not None:
        pattern_layer = QgsSimpleFillSymbolLayer()
        qt_pattern = getattr(Qt, pattern_style, Qt.FDiagPattern)
        pattern_layer.setBrushStyle(qt_pattern)
        pattern_layer.setColor(pattern_line_color)

    return pattern_layer

def _get_icon(icon, LINE_WIDTH_FACTOR, geom_type=0):
    """
    Erstellt ein Icon-Layer
    geom_type: 0=Point, 1=Line, 2=Polygon
    """
    icon_name = icon.get("icon", "default")

    icon_size = 40
    icon_rotate = icon.get("iconRotate", 0)
    icon_position = icon.get("symbolPlacement", "point")
    icon_spacing = icon.get("iconSpacing", 10) * LINE_WIDTH_FACTOR
    icon_placement = icon.get("symbolPlacement", "point")
    icon_anchor = icon.get("iconAnchor", None)
    icon_offset = icon.get("iconOffset", (0, 0))
    icon_label = icon.get("mapLabel", None)
    
    icon_url = f"{BASE_ICON_URL}{icon_name}.png"
    
    # Für Polygone mit iconPosition "center" -> Centroid
    if geom_type == 2 and icon_position == "point":
        marker_symbol = QgsMarkerSymbol()
        marker_symbol.deleteSymbolLayer(0)
        
        icon_layer = QgsRasterMarkerSymbolLayer(icon_url)
        icon_layer.setSize(icon_size)
        icon_layer.setAngle(icon_rotate)
        
        icon_layer.setSizeUnit(QgsUnitTypes.RenderPixels)
        icon_layer.setOffsetUnit(QgsUnitTypes.RenderPixels)
        
        if icon_offset and len(icon_offset) == 2:
            # Y-Achse invertieren für korrekte Richtung
            icon_layer.setOffset(QPointF(
                icon_offset[0] * LINE_WIDTH_FACTOR, 
                -icon_offset[1] * LINE_WIDTH_FACTOR  # MINUS für Y!
            ))
        
        marker_symbol.appendSymbolLayer(icon_layer)
        
        centroid_fill = QgsCentroidFillSymbolLayer()
        centroid_fill.setSubSymbol(marker_symbol)
        centroid_fill.setPointOnSurface(False)
        
        return centroid_fill
    
    # Für Linien mit Icons entlang der Linie ODER Polygone mit Icons an der Kante
    if (icon_placement == "line"):
        marker_symbol = QgsMarkerSymbol()
        marker_symbol.deleteSymbolLayer(0)

        icon_layer = QgsRasterMarkerSymbolLayer(icon_url)
        icon_layer.setSize(icon_size* 2) 
        icon_layer.setAngle(icon_rotate)
        
        icon_layer.setSizeUnit(QgsUnitTypes.RenderPercentage)
        icon_layer.setOffsetUnit(QgsUnitTypes.RenderPercentage)
        
        if icon_offset and len(icon_offset) == 2:
            # Y-Achse invertieren
            if(icon_rotate == 180):
                y_offset =  float(icon_offset[1] * LINE_WIDTH_FACTOR)
            else:
                y_offset =  -float(icon_offset[1] * LINE_WIDTH_FACTOR)
                
            x_offset = float(icon_offset[0] * LINE_WIDTH_FACTOR)
            
            
            
            icon_layer.setOffset(QPointF(x_offset, y_offset))
        
        marker_symbol.appendSymbolLayer(icon_layer)
        
        marker_line = QgsMarkerLineSymbolLayer()
        marker_line.setSubSymbol(marker_symbol)
        
        marker_line.setIntervalUnit(QgsUnitTypes.RenderPixels)
        
        if icon_placement == "line":
            marker_line.setInterval(icon_spacing * 3)
            marker_line.setPlacement(QgsMarkerLineSymbolLayer.Interval)
            
            # WICHTIG: Rotation mit Linie aktivieren für korrekte Ausrichtung
            marker_line.setRotateSymbols(True)
        else:
            marker_line.setPlacement(QgsMarkerLineSymbolLayer.CentralPoint)
        
        return marker_line
    
    # Standard: Einzelnes Icon für Points
    icon_layer = QgsRasterMarkerSymbolLayer(icon_url)
    icon_layer.setSize(icon_size)
    icon_layer.setAngle(icon_rotate)
    
    icon_layer.setSizeUnit(QgsUnitTypes.RenderPixels)
    icon_layer.setOffsetUnit(QgsUnitTypes.RenderPixels)
    
    if icon_offset and len(icon_offset) == 2:
        # Y-Achse invertieren
        icon_layer.setOffset(QPointF(
            icon_offset[0] * LINE_WIDTH_FACTOR, 
            -icon_offset[1] * LINE_WIDTH_FACTOR  # MINUS für Y!
        ))
    
    return icon_layer