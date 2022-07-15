# flake8: noqa
import tempfile
import os


""" sets a temporary directory for use within the client """
TEMP_DIR = f"{tempfile.gettempdir()}{os.path.sep}onscale_client"


def is_jupyter() -> bool:
    try:
        from IPython import get_ipython  # type: ignore
        from ipykernel.zmqshell import ZMQInteractiveShell  # type: ignore

        shell = get_ipython()
        if isinstance(shell, ZMQInteractiveShell):
            return True
        return False
    except ImportError:
        return False


def import_tqdm_notebook() -> bool:
    if is_jupyter():
        try:
            import ipywidgets  # type: ignore
        except ImportError:
            return False
        return True
    else:
        return False


class ClientSettings:
    __instance = None

    @staticmethod
    def getInstance():
        """Static access method."""
        if ClientSettings.__instance is None:
            ClientSettings()
        return ClientSettings.__instance

    def __init__(self, quiet_mode: bool = False, debug_mode: bool = False):
        """Virtually private constructor."""
        if ClientSettings.__instance is not None:
            pass
        else:
            self.quiet_mode = quiet_mode
            self.debug_mode = debug_mode

            self.is_jupyter = is_jupyter()

            ClientSettings.__instance = self
