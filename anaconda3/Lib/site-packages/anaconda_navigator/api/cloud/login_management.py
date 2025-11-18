# -*- coding: utf8 -*-

"""Utilities to manage login workflows and states."""

from __future__ import annotations

__all__ = ['LoginManager', 'LOGIN_MANAGER']

import typing

from qtpy import QtCore

from anaconda_navigator import config
from anaconda_navigator.utils import singletons
from anaconda_navigator.utils import telemetry
from anaconda_navigator.utils import workers
from anaconda_navigator.utils.logs import logger
from . import api


class LoginManager(QtCore.QObject):
    """Manage .cloud login flow."""

    sig_login_started = QtCore.Signal()
    sig_login_succeeded = QtCore.Signal(workers.TaskResult)
    sig_login_canceled = QtCore.Signal(workers.TaskResult)
    sig_login_failed = QtCore.Signal(workers.TaskResult)
    sig_login_done = QtCore.Signal(workers.TaskResult)

    sig_logout = QtCore.Signal()

    sig_state_changed = QtCore.Signal(bool)

    sig_throttle_started = QtCore.Signal()
    sig_throttle_finished = QtCore.Signal()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        """Initialize new instance of a :class:`~CloudLoginManager`."""
        super().__init__(parent=parent)

        self.__pending: bool = False
        self.__worker: workers.TaskWorker | None = None

        self.__throttle: bool = False

        self.__throttle_timer: typing.Final[QtCore.QTimer] = QtCore.QTimer(self)
        self.__throttle_timer.setInterval(5_000)  # 5 seconds
        self.__throttle_timer.setSingleShot(True)
        self.__throttle_timer.timeout.connect(self.__stop_throttle)

    # login

    def login(self, origin: str = 'unknown') -> None:
        """Start a login process."""
        if self.__throttle:
            logger.debug('cloud login throttled')
            return
        logger.debug('cloud login initiated')

        telemetry.ANALYTICS.instance.event('cloud-login-requested', {'origin': origin})
        if self.__worker is not None:
            self.__pending = True
            self.__worker.cancel()
        else:
            self.__login()

    def __login(self) -> None:
        """Initialize a worker to process login workflow."""
        self.__start_throttle()

        self.__worker = typing.cast(workers.TaskWorker, api.CloudAPI().login.worker())
        self.__worker.signals.sig_start.connect(self.sig_login_started)
        self.__worker.signals.sig_succeeded.connect(self.sig_login_succeeded)
        self.__worker.signals.sig_canceled.connect(self.sig_login_canceled)
        self.__worker.signals.sig_failed.connect(self.sig_login_failed)
        self.__worker.signals.sig_done.connect(self.__login_done)
        self.__worker.start()

    def __login_done(self, result: workers.TaskResult) -> None:
        """Process result of a login processing."""
        self.__stop_throttle()
        self.__worker = None
        self.sig_login_done.emit(result)

        if result.status == workers.TaskStatus.SUCCEEDED:
            logger.debug('cloud login succeeded')
            telemetry.ANALYTICS.instance.event(
                'login_changed', {
                    'action': telemetry.AccountAction.LOGIN,
                    'edition': config.AnacondaBrand.CLOUD,
                }, user_properties={'cloud-edition': config.AnacondaBrand.CLOUD})
            self.sig_state_changed.emit(True)
        elif result.status == workers.TaskStatus.CANCELED:
            if self.__pending:
                self.__pending = False
                self.__login()

            logger.debug('cloud login canceled')
            telemetry.ANALYTICS.instance.event('cancel-cloud-login')
        elif result.status == workers.TaskStatus.FAILED:
            logger.debug('cloud login failed')
            telemetry.ANALYTICS.instance.event('cloud-login-failed')
        else:  # just in case we add new status and forget to add it here
            logger.debug('cloud login done')  # type: ignore

    # logout

    def logout(self) -> None:
        """Log out from .cloud account."""
        if not api.CloudAPI().token:
            logger.debug('cloud logout ignored')
            return
        logger.debug('cloud logout initiated')

        if self.__worker is not None:
            self.__worker.cancel()

        api.CloudAPI().logout()
        telemetry.ANALYTICS.instance.event(
            'login_changed', {
                'action': telemetry.AccountAction.LOGOUT,
                'edition': config.AnacondaBrand.CLOUD,
            },
            user_properties={'cloud-edition': '-'})
        self.sig_logout.emit()
        self.sig_state_changed.emit(False)
        logger.debug('cloud logout succeeded')

    # throttle

    def __start_throttle(self) -> None:
        """
        Start login process throttling.

        It doesn't allow to spam logins by giving each login attempt 5 seconds to start.
        """
        if self.__throttle:
            return
        logger.debug('cloud login throttling started')
        self.__throttle = True
        self.__throttle_timer.start()
        self.sig_throttle_started.emit()

    def __stop_throttle(self) -> None:
        """Finish login throttling."""
        if not self.__throttle:
            return
        logger.debug('cloud login throttling finished')

        self.__throttle_timer.stop()
        self.__throttle = False
        self.sig_throttle_finished.emit()


LOGIN_MANAGER: typing.Final[singletons.Singleton[LoginManager]] = singletons.SingleInstanceOf(LoginManager)
