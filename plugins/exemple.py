from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen


def register(api):
    def draw_border(window):
        doc = window.doc
        if doc is None:
            return
        layer = doc.active_layer()
        if layer is None or layer.locked:
            window.notify("Calque verrouillé")
            return
        tx = doc.history.begin("Plugin : bordure")
        tx.touch(layer, doc.rect())
        painter = QPainter(layer.image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(window.fg), 12))
        painter.drawRect(6, 6, doc.size.width() - 12, doc.size.height() - 12)
        painter.end()
        doc.invalidate_all()
        tx.commit()
        window.notify("Bordure ajoutée par le plugin")

    api.add_action("Plugin : ajouter une bordure", draw_border)
