# -*- coding: utf8 -*-

"""Components to manage "what's new" updates."""

from __future__ import annotations

__all__ = ['WhatsNewComponent']

import json
import typing

import attrs.setters
from qtpy import QtCore

from anaconda_navigator import __about__
from anaconda_navigator.api.cloud import login_management
from anaconda_navigator.config import CONF, preferences, feature_flags
from anaconda_navigator.utils import attribution
from anaconda_navigator.utils import download_manager
from anaconda_navigator.widgets.web import whats_new as whats_new_dialogs
from anaconda_navigator.widgets.web import links
from . import common

if typing.TYPE_CHECKING:
    import typing_extensions
    from anaconda_navigator.widgets import main_window


class State(typing.TypedDict, total=False):
    """Local state of what's new updates."""

    cloud_login_popup_state: int
    cloud_login_popup_ts: int


class ClientState(typing.TypedDict):
    """
    State of the current user.

    Used to decide which updates to show.

    .. warning::

        Must not include any PII!
    """

    accounts: list[str]
    navigator_version: str
    state: State


class Selection(typing.TypedDict):
    """
    Selection of updates to show to the user.

    Retrieved from the server.
    """

    state: typing_extensions.NotRequired[State]
    updates: list[whats_new_dialogs.Update]


@attrs.define(on_setattr=attrs.setters.frozen)
class Request:  # pylint: disable=too-few-public-methods
    """
    Details on how to show a "what's new" dialog.

    :param respect_settings: Skip the pop-up if the user selected to "Hide "what's new" dialog on startup".
    :param skip_empty: Skip the pop-up if there are no applicable updates.
    :param updates_only: Skip updates that user already saw.
    """

    respect_settings: bool = attrs.field(default=False, kw_only=True)
    skip_empty: bool = attrs.field(default=False, kw_only=True)
    updates_only: bool = attrs.field(default=False, kw_only=True)

    ready: bool = attrs.field(default=False, init=False, on_setattr=attrs.setters.NO_OP)


class WhatsNewComponent(common.Component):
    """Component to manage what's new content and pop up."""

    __alias__ = 'whats_new'

    def __init__(self, parent: main_window.MainWindow) -> None:
        """Initialize new instance of a :class:`~UpdatesComponent`."""
        super().__init__(parent)

        self.__content: Selection = {'updates': []}
        self.__dialog: whats_new_dialogs.WhatsNewDialog | None = None

        self.__request: Request | None = None
        self.__suspended: bool = True

        self.__timer: QtCore.QTimer = QtCore.QTimer()
        self.__timer.setInterval(3_000)
        self.__timer.setSingleShot(True)
        self.__timer.timeout.connect(self.__push_dialog)

    def fetch(self) -> None:
        """Retrieve latest updates from the server."""
        client_state: ClientState = {
            'accounts': self.main_window.components.accounts.list_accounts(),
            'navigator_version': __about__.__version__,
            'state': {  # type: ignore
                key: CONF.get('internal', key)
                for key in State.__annotations__
            },
        }

        download: download_manager.Download = (
            download_manager.Download(preferences.UPDATES_LINK)
            .attach('POST', json.dumps(client_state))
            .extra(headers={'Content-Type': 'application/json', **feature_flags.prepare_headers()})
            .via(download_manager.Medium.MEMORY)
        )
        download.sig_succeeded.connect(lambda response: self.__process_content(response.content))
        download_manager.MANAGER.instance.execute(download, force=True)

    @typing.overload
    def show(self, request: Request) -> None:
        """Request to show a "what's new" pop up."""

    @typing.overload
    def show(self, *, respect_settings: bool = ..., skip_empty: bool = ..., updates_only: bool = ...) -> None:
        """Request to show a "what's new" pop up."""

    def show(
            self,
            request: Request | None = None,
            *,
            respect_settings: bool = False,
            skip_empty: bool = False,
            updates_only: bool = False,
    ) -> None:
        """
        Request to show a "what's new" pop up.

        Refer to :class:`~Request` for details on arguments.
        """
        if request is None:
            request = Request(respect_settings=respect_settings, skip_empty=skip_empty, updates_only=updates_only)
        if request.respect_settings and CONF.get('main', 'hide_whats_new_dialog'):
            return
        self.__hide_dialog()
        self.__request = request
        self.__timer.start()
        self.fetch()

    def setup(self, worker: typing.Any, output: typing.Any, error: str, initial: bool) -> None:
        """Perform component configuration from `conda_data`."""
        self.__suspended = False
        self.__show_dialog()

    def __process_content(self, content: bytes) -> None:
        """Process response from the server with a new content."""
        try:
            self.__content = json.loads(content)
        except ValueError:
            pass
        self.__push_dialog()

    def __push_dialog(self) -> None:
        """
        Mark requested pop-up as ready to be shown.

        .. note::

            Should be requested after the content is fetched, or after the timeout is reached.
        """
        if self.__request is not None:
            self.__request.ready = True
            self.__show_dialog()

    def __show_dialog(self) -> None:
        """Show requested content in a "what's new" popup."""
        request: Request | None = self.__request
        if self.__suspended or (request is None) or (not request.ready):
            return
        self.__request = None

        # Check if dialog should be skipped due to application settings
        if request.respect_settings and CONF.get('main', 'hide_whats_new_dialog'):
            return

        # Collect updates to include in a dialog
        updates: list[whats_new_dialogs.Update] = self.__content['updates'][:]

        # Skip seen updates if requested
        if request.updates_only:
            seen: set[str] = set(CONF.get('internal', 'whats_new_seen'))

            new_seen: set[str] = set()
            new_updates: list[whats_new_dialogs.Update] = []

            update: whats_new_dialogs.Update
            for update in updates:
                if update['id'] in seen:
                    new_seen.add(update['id'])
                else:
                    new_updates.append(update)

            CONF.set('internal', 'whats_new_seen', sorted(new_seen))
            updates = new_updates

        # Do not show empty dialog if requested
        if request.skip_empty and (not updates):
            return

        self.__dialog = whats_new_dialogs.WhatsNewDialog(content=updates)
        self.__dialog.rejected.connect(self.__hide_dialog)
        self.__dialog.sig_navigator_link_requested.connect(self.__process_navigator_link)
        self.__dialog.show()

        key: str
        state: State = self.__content.pop('state', {})
        for key in State.__annotations__:
            if key in state:
                CONF.set('internal', key, state[key])  # type: ignore

    def __hide_dialog(self) -> None:
        """Hide currently visible "what's new" dialog."""
        if self.__dialog is not None:
            self.__dialog.hide()
            self.__dialog.deleteLater()
            self.__dialog = None

    def __process_navigator_link(self, link: links.NavigatorLink) -> None:
        """
        Process a :code:`navigator://` action triggered from the "what's new" pop-up.

        .. note::

            Implemented on this level to provide access to the main window, other components, and dialog itself (in
            case it should be closed).
        """
        if link.path == ('cloud', 'sign-in'):
            login_management.LOGIN_MANAGER.instance.login(origin='whats-new')
            self.__hide_dialog()
            return

        if link.path == ('cloud', 'sign-up'):
            url: str = attribution.POOL.settings.inject_url_parameters(
                'https://anaconda.cloud/sign-up',
                utm_medium='connect-cloud',
                utm_content='signup',
            )
            links.open_link(url, origin='whats-new')
            return
