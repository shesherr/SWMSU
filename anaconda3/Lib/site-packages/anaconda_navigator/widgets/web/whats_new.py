# -*- coding: utf8 -*-

"""Implementation of a "What's new" dialog."""

from __future__ import annotations

__all__ = ['Update', 'WhatsNewDialog']

import collections.abc
import functools
import io
import typing

import attrs

from qtpy import QtCore
from qtpy import QtWebEngineWidgets
from qtpy import QtWidgets

from anaconda_navigator.static import content as static_content
from anaconda_navigator.config import CONF
from anaconda_navigator import widgets
from anaconda_navigator.widgets import dialogs
from . import common

if typing.TYPE_CHECKING:
    import typing_extensions


def mode() -> typing.Literal['light', 'dark']:
    """Detect the current mode."""
    if CONF.get('main', 'dark_mode'):
        return 'dark'
    return 'light'


def prepare_url(url: str) -> QtCore.QUrl:
    """Prepare URL with injected details on light/dark mode."""
    result: QtCore.QUrl = QtCore.QUrl(url)
    query: QtCore.QUrlQuery = QtCore.QUrlQuery(result.query())
    query.addQueryItem('theme', mode())
    result.setQuery(query)
    return result


class IndexHelper:
    """
    Helper class to manage indexes of visible navigation dots.

    This is needed for cases when we can show fewer dots that we actually need to (e.g. we only have space for 7 dots,
    but we have 11 pages). Works for valid cases as well (i.e. we have enough space for all dots)

    It basically replaces all excessive dots in the middle with a visible dot in the center. This dot is selected when
    any page from the middle is active, and activates the first page of the "middle group" when clicked.

    :param total: The total number of dots that ideally should be rendered.
    :param allowed: The maximum number of dots we can actually draw.
    """

    __slots__ = ('delta', 'left', 'right', 'total')

    def __init__(self, total: int, allowed: int) -> None:
        """Initialize new instance of a :class:`~IndexHelper`."""
        allowed = min(allowed, total)

        self.delta: typing.Final[int] = allowed - total
        self.left: typing.Final[int] = allowed - (allowed // 2) - 1
        self.right: typing.Final[int] = total - (allowed // 2)
        self.total: typing.Final[int] = total

    def __call__(self, index: int) -> int:
        """Retrieve index of a visible dot when :code:`index` page is selected."""
        if index <= self.left:
            return index
        if index < self.right:
            return self.left
        return index + self.delta

    def __iter__(self) -> collections.abc.Iterator[int]:
        """Iterate through page indexes each visible dot represents."""
        yield from range(self.left + 1)
        yield from range(self.right, self.total)


class Update(typing.TypedDict):
    """
    Description of a single update to show.

    .. note::

        Should be retrieved from the server.
    """

    id: str
    title: str
    url: str


@attrs.frozen
class UpdatePage:  # pylint: disable=too-few-public-methods
    """Container for all details related to a single page with updates."""

    info: Update
    page: common.ExtendedWebEnginePage = attrs.field(
        factory=functools.partial(common.ExtendedWebEnginePage, origin='whats-new'),
        init=False,
    )

    def load(self) -> None:
        """Request to load a web page."""
        self.page.load(prepare_url(self.info['url']))


@attrs.frozen
class UpdatePageWithContent(UpdatePage):
    """Custom :class:`~UpdatePage` with a predefined web-page content."""

    content: bytes

    @classmethod
    def from_file(
            cls,
            path: str,
            *,
            title: str = 'What\'s new',
            url: str = 'navigator://content',
            identity: str = ':content:',
    ) -> typing_extensions.Self:
        """Load a web-page from a file."""
        stream: io.BufferedReader
        with open(path, 'rb') as stream:
            content: bytes = stream.read()
        return cls(content=content, info={'id': identity, 'title': title, 'url': url})

    def load(self) -> None:
        """Request to load a web page."""
        self.page.setContent(self.content, 'text/html', prepare_url(self.info['url']))


class WhatsNewDialog(dialogs.DialogBase):  # pylint: disable=too-many-instance-attributes
    """
    Dialog for a "what's new" content.

    :param content: Updates to show in the dialog. If none provided - will fall back to the "whats_new_empty" page.
    """

    sig_navigator_link_requested = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None, content: collections.abc.Iterable[Update] = ()) -> None:
        """Initialize new instance of a :class:`~WhatsNewDialog`."""
        super().__init__(parent)

        pages: list[UpdatePage] = list(map(UpdatePage, content))
        if not pages:
            pages.append(UpdatePageWithContent.from_file(static_content.WHATS_NEW_EMPTY_PAGE))

        self.__pages: typing.Final[tuple[UpdatePage, ...]] = tuple(pages)
        self.__page_index: int = -1
        self.__page_index_helper: typing.Final[IndexHelper] = IndexHelper(len(self.__pages), 7)  # max dots

        self.__pending: bool = False
        self.__ready: bool = False

        # interface

        self.__web_view: typing.Final[QtWebEngineWidgets.QWebEngineView] = QtWebEngineWidgets.QWebEngineView()

        self.__previous_button: typing.Final[QtWidgets.QPushButton] = widgets.ButtonNormal()
        self.__previous_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.__previous_button.setText('< prev')
        self.__previous_button.clicked.connect(lambda: self.__set_page(self.page_index - 1))

        self.__navigation_dots: typing.Final[tuple[widgets.DotControlButton, ...]] = tuple(
            map(self.__create_dot, self.__page_index_helper),
        )

        self.__next_button: typing.Final[QtWidgets.QPushButton] = widgets.ButtonNormal()
        self.__next_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.__next_button.setText('next >')
        self.__next_button.clicked.connect(lambda: self.__set_page(self.page_index + 1))

        control_layout: typing.Final[QtWidgets.QHBoxLayout] = QtWidgets.QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(24)
        control_layout.addWidget(self.__previous_button)
        control_layout.addStretch(1)
        for navigation_dot in self.__navigation_dots:
            control_layout.addWidget(navigation_dot)
        control_layout.addStretch(1)
        control_layout.addWidget(self.__next_button)

        main_layout: typing.Final[QtWidgets.QVBoxLayout] = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.__web_view, 1)
        main_layout.addSpacing(16)
        main_layout.addLayout(control_layout)

        self.label_title_bar.setText('What\'s new')
        self.setFixedSize(600, 800)
        self.setLayout(main_layout)

        # initialize content
        pages[0].page.loadFinished.connect(self.__set_ready)

        page: UpdatePage
        for page in self.__pages:
            page.page.sig_navigator_link_requested.connect(self.sig_navigator_link_requested)
            page.load()

        self.page_index = 0

    @property
    def page_index(self) -> int:  # noqa: D401
        """Index of a current page displayed."""
        return self.__page_index

    @page_index.setter
    def page_index(self, value: int) -> None:
        """Switch to a specific update page."""
        value %= len(self.__pages)

        # update dots
        self.__navigation_dots[self.__page_index_helper(self.__page_index)].setChecked(False)
        self.__navigation_dots[self.__page_index_helper(value)].setChecked(True)

        # skip further processing if page did not change
        if value == self.__page_index:
            return

        # show selected page
        page: UpdatePage = self.__pages[value]
        self.label_title_bar.setText(page.info['title'])
        self.__web_view.setPage(page.page)

        # update buttons
        self.__previous_button.setEnabled(value > 0)
        self.__next_button.setEnabled(value + 1 < len(self.__pages))

        # mark current page as seen
        seen: set[str] = set(CONF.get('internal', 'whats_new_seen'))
        seen.add(page.info['id'])
        CONF.set('internal', 'whats_new_seen', sorted(seen))

        # remember current value
        self.__page_index = value

    def show(self) -> None:
        """Show this dialog to the user."""
        if self.__ready:
            super().show()
        else:
            self.__pending = True

    def __create_dot(self, index: int) -> widgets.DotControlButton:
        """Create a new navigation dot."""
        result: widgets.DotControlButton = widgets.DotControlButton()
        result.clicked.connect(lambda: self.__set_page(index))
        return result

    def __set_page(self, index: int) -> None:
        """
        Switch to an update page.

        .. note::

            Used for lambdas connected to signals.
        """
        self.page_index = index

    def __set_ready(self) -> None:
        """
        Mark a widget as ready to be displayed.

        .. note::

            Should be called after at least a first update page is loaded.
        """
        self.__ready = True
        if self.__pending:
            self.__pending = False
            self.show()
