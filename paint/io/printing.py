from __future__ import annotations

from PySide6.QtCore import QMarginsF, QRect, QSizeF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter


def _configure(printer: QPrinter, doc) -> None:
    dpi = max(36, int(doc.dpi or 96))
    width_mm = doc.size.width() / dpi * 25.4
    height_mm = doc.size.height() / dpi * 25.4
    printer.setResolution(300)
    printer.setPageOrientation(
        QPageLayout.Landscape if width_mm > height_mm else QPageLayout.Portrait)
    printer.setPageSize(QPageSize(QSizeF(width_mm, height_mm), QPageSize.Millimeter,
                                 "Feuille", QPageSize.ExactMatch))
    printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)


def _paint(doc, printer: QPrinter) -> None:
    painter = QPainter(printer)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    page = printer.pageLayout().paintRectPixels(printer.resolution())
    target = QRect(page)
    image = doc.composite()
    scaled = image.size().scaled(target.size(), Qt.KeepAspectRatio)
    x = target.x() + (target.width() - scaled.width()) // 2
    y = target.y() + (target.height() - scaled.height()) // 2
    painter.fillRect(page, QColor("#ffffff"))
    painter.drawImage(QRect(x, y, scaled.width(), scaled.height()), image)
    painter.end()


def print_document(doc, parent=None, preview: bool = False) -> bool:
    printer = QPrinter(QPrinter.HighResolution)
    if doc.path is not None:
        printer.setDocName(doc.path.name)
    else:
        printer.setDocName("Sans titre")
    _configure(printer, doc)
    if preview:
        dialog = QPrintPreviewDialog(printer, parent)
        dialog.setWindowTitle("Aperçu avant impression")
        dialog.paintRequested.connect(lambda target: _paint(doc, target))
        dialog.exec()
        return True
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Imprimer")
    if dialog.exec() != QPrintDialog.Accepted:
        return False
    _paint(doc, printer)
    return True
