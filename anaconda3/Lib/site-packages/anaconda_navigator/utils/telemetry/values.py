"""Store telemetry-related values."""

__all__ = ['AccountAction']

import enum


class AccountAction(str, enum.Enum):
    """Login actions."""

    LOGIN = 'loging'
    LOGOUT = 'logout'
    DETECTED = 'detected'
    DETECTED_LOGIN = 'detected-login'
    DETECTED_LOGOUT = 'detected-logout'
