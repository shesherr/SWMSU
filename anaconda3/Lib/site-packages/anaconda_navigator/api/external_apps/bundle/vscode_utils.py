# -*- coding: utf-8 -*-

"""Additional utility functions to use with pycharm."""

from __future__ import annotations

__all__ = ['vscode_extra_arguments', 'vscode_install_extensions', 'vscode_update_config']

import datetime
import json
import os
import typing
from anaconda_navigator import config as navigator_config
from anaconda_navigator.api import conda_api
from anaconda_navigator.utils.logs import logger

if typing.TYPE_CHECKING:
    from anaconda_navigator.api import process
    from .. import base


def vscode_extra_arguments() -> typing.Sequence[str]:
    """Return default extra arguments for vscode."""
    return '--user-data-dir', os.path.join(navigator_config.CONF_PATH, 'Code')


def vscode_update_config(instance: 'base.BaseInstallableApp', prefix: str) -> None:  # pylint: disable=unused-argument
    """Update user config to use selected Python prefix interpreter."""
    try:
        _config_dir: str = os.path.join(navigator_config.CONF_PATH, 'Code', 'User')
        _config: str = os.path.join(_config_dir, 'settings.json')

        try:
            os.makedirs(_config_dir, exist_ok=True)
        except OSError as exception:
            logger.error(exception)
            return

        stream: typing.TextIO
        config_data: typing.Dict[str, typing.Any]
        if os.path.isfile(_config):
            try:
                with open(_config, 'rt', encoding='utf-8') as stream:
                    data = stream.read()
                vscode_create_config_backup(data)

                config_data = json.loads(data)
            except BaseException:  # pylint: disable=broad-except
                return
        else:
            config_data = {}

        pyexec: str = conda_api.get_pyexec(prefix)
        config_data.update({
            'python.experiments.optInto': ['pythonTerminalEnvVarActivation'],
            'python.terminal.activateEnvInCurrentTerminal': True,
            'python.terminal.activateEnvironment': True,
            'python.pythonPath': pyexec,
            'python.defaultInterpreterPath': pyexec,
            'python.condaPath': conda_api.get_pyscript(conda_api.CondaAPI().ROOT_PREFIX, 'conda'),
        })
        with open(_config, 'wt', encoding='utf-8') as stream:
            json.dump(config_data, stream, sort_keys=True, indent=4)

    except Exception as exception:  # pylint: disable=broad-except
        logger.error(exception)
        return


def vscode_create_config_backup(data: str) -> None:
    """
    Create a backup copy of the app configuration file `data`.

    Leave only the last 10 backups.
    """
    date: str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    _config_dir: str = os.path.join(navigator_config.CONF_PATH, 'Code', 'User')
    _config_bck: str = os.path.join(_config_dir, f'bck.{date}.navigator.settings.json')

    # Make the backup
    stream: typing.TextIO
    with open(_config_bck, 'wt', encoding='utf-8') as stream:
        stream.write(data)

    # Only keep the latest 10 backups
    files: typing.List[str] = [
        os.path.join(_config_dir, item)
        for item in os.listdir(_config_dir)
        if item.startswith('bck.') and item.endswith('.navigator.settings.json')
    ]
    path: str
    for path in sorted(files, reverse=True)[10:]:
        try:
            os.remove(path)
        except OSError:
            pass


def vscode_install_extensions(instance: 'base.BaseInstallableApp') -> 'process.ProcessWorker':
    """Install app extensions."""
    if instance.executable is None:
        return instance._process_api.create_process_worker(['python', '--version'])  # pylint: disable=protected-access

    cmd: typing.Sequence[str] = [
        instance.executable,
        '--install-extension',
        # 'ms-python.anaconda-extension-pack',
        # 'ms-python-anaconda-extension',
        'ms-python.python',
    ]
    return instance._process_api.create_process_worker(cmd)  # pylint: disable=protected-access
