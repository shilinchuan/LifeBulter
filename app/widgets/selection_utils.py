from PyQt6.QtCore import QObject, QEvent, QTimer
from PyQt6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QDateEdit, QDoubleSpinBox, QLineEdit,
    QListWidget, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTextEdit,
)


KEEP_SELECTION_FOCUS_WIDGETS = (
    QPushButton,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QDateEdit,
)


class ClearSelectionFilter(QObject):
    """Clear row/list selection when focus leaves or empty viewport is clicked."""

    def __init__(self, view: QAbstractItemView):
        super().__init__(view)
        self.view = view

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusOut:
            QTimer.singleShot(0, self._clear_unless_button_focus)
        elif event.type() == QEvent.Type.MouseButtonPress and obj is self.view.viewport():
            index = self.view.indexAt(event.pos())
            if not index.isValid():
                self.clear()
        return False

    def clear(self):
        self.view.clearSelection()
        if isinstance(self.view, QTableWidget):
            self.view.setCurrentCell(-1, -1)
        elif isinstance(self.view, QListWidget):
            self.view.setCurrentRow(-1)
        else:
            self.view.setCurrentIndex(self.view.model().index(-1, -1))

    def _clear_unless_button_focus(self):
        focus = QApplication.focusWidget()
        while focus is not None:
            if isinstance(focus, KEEP_SELECTION_FOCUS_WIDGETS):
                return
            focus = focus.parentWidget()
        self.clear()


def enable_clear_selection_on_blur(view: QAbstractItemView):
    filter_obj = ClearSelectionFilter(view)
    view.installEventFilter(filter_obj)
    view.viewport().installEventFilter(filter_obj)
    filters = getattr(view, "_lifebutler_selection_filters", [])
    filters.append(filter_obj)
    view._lifebutler_selection_filters = filters
    return filter_obj
