"""Base and styling dialogs for login reminders."""
from __future__ import annotations

import typing

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QFrame, QWidget, QLabel, QVBoxLayout, QLayout

from anaconda_navigator.widgets import FrameBase
from anaconda_navigator.widgets.dialogs import ButtonDialogClose


class SeparatorLine(QFrame):
    """Frame widget used for CSS styling widgets like QFrame.HLine/QFrame.VLine"""


class CleanDialogTitle(QLabel):
    """Frame widget used for CSS styling of the title."""


class CleanDialogFrame(FrameBase):
    """Frame widget used for CSS styling of the body dialogs."""


class CleanDialogBodyFrame(FrameBase):
    """Frame widget used for CSS styling of the body."""


class CleanDialogHeaderFrame(FrameBase):
    """Frame widget used for CSS styling of the title bar of dialogs."""


class BaseCleanDialog(QDialog):  # pylint: disable=too-many-instance-attributes
    """Base class for clean dialogs."""
    def __init__(self, parent: typing.Optional[QWidget] = None, title: str = '') -> None:
        """Initialize new :class:`~BaseCleanDialog` instance."""
        super().__init__(parent)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setSizeGripEnabled(False)
        self.setWindowFlags(Qt.MSWindowsFixedSizeDialogHint)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)

        self.__close_button = ButtonDialogClose()
        self.__close_button.setFocusPolicy(Qt.NoFocus)

        self.__title_label = CleanDialogTitle(title)

        self.__separator_line = SeparatorLine()
        self.__separator_line.setFrameShape(QFrame.HLine)
        self.__separator_line.setFrameShadow(QFrame.Sunken)

        self.__main_frame = CleanDialogFrame(self)
        self.__header_frame = CleanDialogHeaderFrame(self)
        self.__body_frame = CleanDialogBodyFrame(self)

        self.__layout = QVBoxLayout()
        self.__header_layout = QVBoxLayout()

        self.__header_layout.setAlignment(Qt.AlignTop)
        self.__header_layout.setSpacing(0)
        self.__header_layout.setContentsMargins(0, 0, 0, 0)
        self.__header_layout.addWidget(self.__title_label, alignment=Qt.AlignLeft)
        self.__header_layout.addWidget(self.__separator_line)

        self.__close_button.clicked.connect(self.reject)

    def setLayout(self, *args: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=invalid-name
        """Set the layout of the body frame."""
        self.__header_frame.setLayout(self.__header_layout)
        self.__body_frame.setLayout(*args, **kwargs)
        self.__main_frame.setLayout(self.__layout)

        self.__layout.addWidget(self.__close_button, alignment=Qt.AlignRight)
        self.__layout.addWidget(self.__header_frame, stretch=2)
        self.__layout.addWidget(self.__body_frame, stretch=8)

        __layout = QVBoxLayout()
        __layout.addWidget(self.__main_frame)
        self.__fix_layout(__layout)

        super().setLayout(__layout)

    def __fix_layout(self, layout: QLayout | None) -> QLayout | None:
        """Remove default spacing."""
        if layout:
            layout.setSpacing(0)
            layout.setContentsMargins(0, 0, 0, 0)

            for w in (layout.itemAt(i).widget() for i in range(layout.count())):
                if w:
                    self.__fix_layout(w.layout())
        return layout
