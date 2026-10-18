"""No display is created by these bootstrap unit tests."""
import pytest

from pne_scheduler.ui.tk_runtime import prepare_tcl


class Interpreter:
    def __init__(self, loaded=False, broken=False):
        self.loaded, self.broken = loaded, broken
        self.calls = []

    def call(self, *args):
        self.calls.append(args)
        if args[:2] == ("info", "commands"):
            return "tcl_findLibrary" if self.loaded else ""
        if args == ("info", "library"):
            return "C:/한글 경로/Tcl library"
        if args[:2] == ("file", "join"):
            return args[2] + "/" + args[3]
        if args[0] == "source":
            if self.broken:
                raise OSError("missing auto.tcl")
            self.loaded = True


def test_windows_finder_loaded_from_active_tcl_not_cwd():
    interpreter = Interpreter()
    prepare_tcl(interpreter, platform="win32")
    assert interpreter.loaded
    assert ("source", "C:/한글 경로/Tcl library/auto.tcl") in interpreter.calls


def test_existing_finder_is_not_replaced():
    interpreter = Interpreter(loaded=True)
    prepare_tcl(interpreter, platform="win32")
    assert len(interpreter.calls) == 2


def test_broken_installation_fails_without_retry_or_skip():
    interpreter = Interpreter(broken=True)
    with pytest.raises(OSError, match="missing auto.tcl"):
        prepare_tcl(interpreter, platform="win32")
    assert len([call for call in interpreter.calls if call[0] == "source"]) == 1


def test_other_platform_uses_normal_tcl_initialization():
    interpreter = Interpreter()
    prepare_tcl(interpreter, platform="darwin")
    assert interpreter.calls == []
