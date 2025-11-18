"""Module for SignalWatcher class."""
from __future__ import annotations

import typing
from qtpy.QtCore import QObject


class SignalWatcher(QObject):
    """A class for connecting to multiple signals."""

    def __init__(
            self,
            callback: typing.Callable[..., typing.Any],
            callback_args: typing.Tuple[typing.Any, ...] | None = None,
            callback_kwargs: typing.Mapping[str, typing.Any] | None = None
    ) -> None:
        """Initialize new :class:`~SignalWatcher`  instance."""
        super().__init__()
        self.__callback: typing.Callable[..., typing.Any] = callback
        self.__signal_control_mapping: typing.MutableMapping[str, bool] = {}

        self.__callback_args: typing.Tuple[typing.Any, ...] = ()
        self.__callback_kwargs: typing.Mapping[str, typing.Any] = {}
        self.__set_callback_arguments(callback_args, callback_kwargs)

    def __set_callback_arguments(
            self,
            callback_args: typing.Tuple[typing.Any, ...] | None,
            callback_kwargs: typing.Mapping[str, typing.Any] | None
    ) -> None:
        self.__callback_args = callback_args if callback_args else self.__callback_args
        self.__callback_kwargs = callback_kwargs if callback_kwargs else self.__callback_kwargs

    def register_signal(self, signal_alias: str) -> None:
        """Register a signal with the watcher."""
        self.__signal_control_mapping[signal_alias] = False

    def signal_received(
            self, signal_alias: str,
            signal_args: typing.Tuple[typing.Any, ...] | None = None,
            signal_kwargs: typing.Mapping[str, typing.Any] | None = None,
            propagate_callback_args: bool = False
    ) -> None:
        """Mark a signal as received and trigger the callback if all signals are received."""
        if signal_alias not in self.__signal_control_mapping:
            return

        self.__signal_control_mapping[signal_alias] = True

        if propagate_callback_args:
            self.__set_callback_arguments(signal_args, signal_kwargs)

        if all(self.__signal_control_mapping.values()):
            self.__callback(*self.__callback_args, *self.__callback_kwargs)
            self.reset()

    def reset(
            self,
            callback_args: typing.Tuple[typing.Any, ...] | None = None,
            callback_kwargs: typing.Mapping[str, typing.Any] | None = None
    ) -> None:
        """Reset received signals control mapping."""
        self.__signal_control_mapping = {}
        self.__set_callback_arguments(callback_args, callback_kwargs)
