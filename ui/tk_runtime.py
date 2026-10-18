"""Explicit Tcl bootstrap shared by the desktop and its GUI tests."""
from __future__ import annotations

import sys
import tkinter as tk


def prepare_tcl(interpreter, *, platform=None):
    """Load Windows' library finder before Tk, without retrying failed tests.

    Tcl 8.6 defines tcl_findLibrary in its own auto.tcl. Windows CI has failed
    inside Tk_Init before any application widget exists because that command
    was not autoloaded. Source the *active interpreter's* library explicitly;
    never guess a Python installation, change global environment variables, or
    suppress a missing/broken Tcl installation. Tcl paths may be virtual paths.
    """
    if (platform or sys.platform) != "win32":
        return
    if not interpreter.call("info", "commands", "tcl_findLibrary"):
        library = interpreter.call("info", "library")
        script = interpreter.call("file", "join", library, "auto.tcl")
        interpreter.call("source", script)
    if not interpreter.call("info", "commands", "tcl_findLibrary"):
        raise tk.TclError("Tcl library does not provide tcl_findLibrary")


def create_root():
    # Tcl first, then Tk: lets a failure identify the actual initialization
    # stage rather than turning an application test into an opaque Tk error.
    root = tk.Tk(useTk=False)
    prepare_tcl(root.tk)
    root.loadtk()
    return root
