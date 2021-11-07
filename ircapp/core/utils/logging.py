import datetime
import os
import sys


def log(txt=""):
    """Import this function to log with log(string)."""
    _Log(txt)


def clear_log():
    """Clear the log."""
    _Log().clear()


def get_log_path() -> str:
    return _Log().my_log


class _Log:
    """Internal only, manage the logging."""

    def __init__(self, txt=""):
        self.text = str(txt)
        if sys.platform == "win32":
            self.my_log = os.path.join(os.environ["LOCALAPPDATA"], "IRCApp", "log.txt")
        else:
            self.my_log = os.path.join(os.path.expanduser("~"), ".IRCApp", "log.txt")

        if self.text:
            self._write()

    def _write(self):
        with open(self.my_log, "a") as f:
            f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + " : " + self.text + "\n")
            f.close()

    def clear(self):
        with open(self.my_log, "w") as f:
            f.write("")
            f.close()
