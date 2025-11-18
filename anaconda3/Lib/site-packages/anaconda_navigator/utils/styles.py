# -*- coding: utf-8 -*-

# pylint: disable=invalid-name

# -----------------------------------------------------------------------------
# Copyright (c) 2016-2017 Anaconda, Inc.
#
# May be copied and distributed freely only as part of an Anaconda or
# Miniconda installation.
# -----------------------------------------------------------------------------

"""Styles for the application."""
from __future__ import annotations

import ast
import contextlib
import os
import re
import string
import typing

from qtpy.QtCore import QSize  # pylint: disable=no-name-in-module
from qtpy.QtGui import QColor, QIcon

from anaconda_navigator.config import CONF
from anaconda_navigator.static import images
from anaconda_navigator.static.css import GLOBAL_SASS_STYLES_PATH, LIGHT_MODE_STYLES_PATH, DARK_MODE_STYLES_PATH

BLUR_SIZE = 10


class SassVariables:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Enum to hold SASS defined variables."""

    def __init__(self) -> None:
        """Enum to hold SASS defined variables."""
        self.SHADOW_BLUR_RADIUS = 7  # Used for dialogs
        self.WIDGET_APPLICATION_TOTAL_HEIGHT = 200
        self.WIDGET_APPLICATION_TOTAL_WIDTH = 200
        self.WIDGET_CONTENT_PADDING = 5
        self.WIDGET_CONTENT_TOTAL_HEIGHT = 200
        self.WIDGET_CONTENT_TOTAL_WIDTH = 200
        self.WIDGET_CONTENT_PADDING = 5
        self.WIDGET_CONTENT_MARGIN = 5
        self.WIDGET_ENVIRONMENT_TOTAL_HEIGHT = 50
        self.WIDGET_IMPORT_ENVIRONMENT_TOTAL_HEIGHT = 55
        self.WIDGET_ENVIRONMENT_TOTAL_WIDTH = 25
        self.WIDGET_APPLICATION_TOTAL_WIDTH = 260
        self.WIDGET_APPLICATION_TOTAL_HEIGHT = 295
        self.WIDGET_CHANNEL_DIALOG_WIDTH = 400
        self.WIDGET_CHANNEL_TOTAL_WIDTH = 300
        self.WIDGET_CHANNEL_TOTAL_HEIGHT = 40
        self.WIDGET_CHANNEL_PADDING = 5
        self.WIDGET_RUNNING_APPS_WIDTH = 450
        self.WIDGET_RUNNING_APPS_TOTAL_WIDTH = 350
        self.WIDGET_RUNNING_APPS_TOTAL_HEIGHT = 55
        self.WIDGET_RUNNING_APPS_PADDING = 10
        self.WIDGET_LOGIN_CARD_TOTAL_WIDTH = 315
        self.WIDGET_LOGIN_CARD_TOTAL_HEIGHT = 200

        self.ICON_ACTION_NOT_INSTALLED = os.path.join(images.STYLED_ICONS_PATH, 'check-box-blank.svg')
        self.ICON_ACTION_INSTALLED = os.path.join(images.IMAGE_PATH, 'icons', 'check-box-checked-active.svg')
        self.ICON_ACTION_REMOVE = os.path.join(images.IMAGE_PATH, 'icons', 'mark-remove.svg')
        self.ICON_ACTION_ADD = os.path.join(images.IMAGE_PATH, 'icons', 'mark-install.svg')
        self.ICON_ACTION_UPGRADE = os.path.join(images.IMAGE_PATH, 'icons', 'mark-upgrade.svg')
        self.ICON_ACTION_DOWNGRADE = os.path.join(images.IMAGE_PATH, 'icons', 'mark-downgrade.svg')
        self.ICON_UPGRADE_ARROW = os.path.join(images.IMAGE_PATH, 'icons', 'update-app-active.svg')
        self.ICON_SPACER = os.path.join(images.IMAGE_PATH, 'conda-manager-spacer.svg')
        self.ICON_PYTHON = os.path.join(images.IMAGE_PATH, 'python-logo.svg')
        self.ICON_ANACONDA = os.path.join(images.IMAGE_PATH, 'anaconda-logo.svg')

        self.COLOR_FOREGROUND_NOT_INSTALLED = '#666'
        self.COLOR_FOREGROUND_UPGRADE = '#00A3E0'
        self.SIZE_ICONS = (32, 32)
        self.STYLED_ICONS_COLOR = '#FFFFFF'

    def process_palette(self) -> dict[str, QIcon | QColor | QSize]:
        """Turn the styles _palette into QIcons or QColors for use in the model."""
        palette: dict[str, QIcon | QColor | QSize] = {}

        for key in dir(self):
            item: QIcon | QColor | QSize | None = None

            if key.startswith('ICON_'):
                item = QIcon(getattr(self, key))
            elif key.startswith('COLOR_'):
                item = QColor(getattr(self, key))
            elif key.startswith('SIZE_'):
                item = QSize(*getattr(self, key))

            if item:
                palette[key] = item

        return palette

    def __repr__(self):
        """Return a pretty formatted representation of the enum."""
        keys = []
        representation = 'SASS variables enum: \n'
        for key in self.__dict__:
            if key[0] in string.ascii_uppercase:
                keys.append(key)

        for key in sorted(keys):
            representation += f'    {key} = {self.__dict__[key]}\n'
        return representation


SASS_VARIABLES = SassVariables()


def flip_icons_color() -> None:
    """Change `fill` of svg icons according to current color pallete."""
    replace_pair: typing.Final[tuple[str, str]] = ('$STYLE_MODE_ICON_COLOR', SASS_VARIABLES.STYLED_ICONS_COLOR)

    for icon_path in os.listdir(images.STYLED_ICON_TEMPLATES_PATH):
        if not icon_path.endswith('.svg'):
            continue

        with open(os.path.join(images.STYLED_ICON_TEMPLATES_PATH, icon_path), 'r', encoding='utf-8') as f:
            svg_icon = f.read().replace(*replace_pair)

        with open(os.path.join(images.STYLED_ICONS_PATH, icon_path), 'w', encoding='utf-8') as f:
            f.write(svg_icon)


def load_sass_variables(path: str) -> SassVariables:
    """Parse Sass file styles and get custom values for used in code."""
    global SASS_VARIABLES  # pylint: disable=global-statement
    SASS_VARIABLES = SassVariables()

    with open(path, 'rt', encoding='utf-8') as f:
        data = f.read()

    pattern = re.compile(r'[$]\S*:.*?;')
    variables = re.findall(pattern, data)
    for var in variables:
        name, value = var[1:-1].split(':')
        if name[0] in string.ascii_uppercase:
            value = value.strip()
            with contextlib.suppress(BaseException):
                value = ast.literal_eval(value)
            setattr(SASS_VARIABLES, name, value)
    return SASS_VARIABLES


def load_style_sheet() -> str:
    """Load css styles file and parse to include custom variables."""
    load_sass_variables(GLOBAL_SASS_STYLES_PATH)
    styles_path = DARK_MODE_STYLES_PATH if CONF.get('main', 'dark_mode', False) else LIGHT_MODE_STYLES_PATH

    with open(styles_path, 'rt', encoding='utf-8') as f:
        data = f.read()

    load_sass_variables(styles_path.replace('.css', '.scss'))
    flip_icons_color()

    styled_image_path = images.DARK_IMAGE_PATH if CONF.get('main', 'dark_mode', False) else images.LIGHT_IMAGE_PATH
    data = data.replace(
        '$IMAGE_PATH', images.IMAGE_PATH.replace('\\', '/') if os.name == 'nt' else images.IMAGE_PATH
    ).replace(
        '$STYLED_IMAGE_PATH', styled_image_path.replace('\\', '/')
        if os.name == 'nt' else styled_image_path
    ).replace(
        '$STYLED_ICONS_PATH', images.STYLED_ICONS_PATH.replace('\\', '/')
        if os.name == 'nt' else images.STYLED_ICONS_PATH
    )

    return data
