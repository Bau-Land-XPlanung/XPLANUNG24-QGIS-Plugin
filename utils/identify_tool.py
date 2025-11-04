# identify_tool.py
from qgis.gui import QgsMapToolIdentify
from qgis.core import QgsWkbTypes
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QCursor


class IdentifyMapTool(QgsMapToolIdentify):
    """Uses QGIS built-in identify logic (same as the native 'i' tool)."""
    featureIdentified = pyqtSignal(list)  # Emits list of (layer_name, gml_id)

    def __init__(self, iface, radius=5):
        super().__init__(iface.mapCanvas())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.radius = radius
        self.setCursor(QCursor(Qt.CrossCursor))

    def canvasReleaseEvent(self, event):
        print("\n=== IdentifyMapTool (built-in QGIS identify) ===")

        # QGIS built-in identify handles CRS and visible layers automatically
        results = self.identify(
            event.x(),
            event.y(),
            self.TopDownAll,    # check all overlapping layers
            self.VectorLayer    # only vector layers
        )

        found = []
        for r in results:
            layer = r.mLayer
            feature = r.mFeature

            # Try to locate a GML ID field (case-insensitive)
            gml_field = None
            for name in feature.fields().names():
                if name.lower() in ["gml_id", "gmlid", "_gml_id", "fid", "id"]:
                    gml_field = name
                    break

            gml_value = feature[gml_field] if gml_field else None
            geom_type = QgsWkbTypes.displayString(feature.geometry().wkbType())

            print(f"Layer: {layer.name()} | Geometry: {geom_type} | "
                  f"GML field: {gml_field} | Value: {gml_value}")

            found.append((layer.name(), gml_value))

        print(f"Total identified: {len(found)}")
        print("==============================================\n")

        self.featureIdentified.emit(found)
