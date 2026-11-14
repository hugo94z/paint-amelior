import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRect, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication

from paint.brush import StampCache, StrokeBuffer, stamps_along
from paint.document import Document
from paint.filters import flood_fill
from paint.io.image_io import export_image


def timed(label, function):
    start = time.perf_counter()
    result = function()
    elapsed = (time.perf_counter() - start) * 1000
    print(f"{label:<42} {elapsed:8.1f} ms")
    return result


def main():
    app = QApplication.instance() or QApplication([])
    width, height = 3840, 2160
    doc = timed("Création du document 4K", lambda: Document.new(width, height, QColor("white")))
    layer = doc.active_layer()
    cache = StampCache(256 * 1024 * 1024)

    stamp = cache.get(24, 0.85, QColor("#111827"))
    points = list(stamps_along(QPointF(10, 10), QPointF(width - 10, height - 10), 3.0))

    def stroke():
        buffer = StrokeBuffer(doc.size)
        for point in points:
            buffer.stamp(stamp, point)
        painter = QPainter(layer.image)
        painter.drawImage(0, 0, buffer.image)
        painter.end()
        return buffer

    buffer = timed(f"Trait de {len(points)} tampons (4K)", stroke)

    def composite():
        doc.invalidate_all()

    timed("Recomposition des calques (4K)", composite)
    timed("Remplissage complet (pot de peinture)", lambda: flood_fill(
        layer.image, 5, 5, QColor("#f97316"), 0
    ))

    tx = doc.history.begin("Bench")
    tx.touch(layer, QRect(0, 0, 512, 512))
    painter = QPainter(layer.image)
    painter.fillRect(QRect(0, 0, 512, 512), QColor("#2563eb"))
    painter.end()
    doc.invalidate(QRect(0, 0, 512, 512))
    tx.commit()
    timed("Annuler une modification 512×512", doc.history.undo)

    target = Path(tempfile.gettempdir()) / "paint-bench.png"
    timed("Export PNG 4K", lambda: export_image(doc, target))
    print(f"Historique : {len(doc.history.labels)} action(s), "
          f"{doc.history.bytes_used() / (1024 * 1024):.1f} Mo")
    target.unlink(missing_ok=True)
    print(f"Threads Qt : {app.thread().currentThread().isRunning()}")
    print(f"Tampons en cache : {len(cache._items)}")


if __name__ == "__main__":
    main()
