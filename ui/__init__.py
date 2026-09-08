"""UI package — visual schedule builder."""

from .flow_model import (
    FlowDurationEstimate,
    FlowProjectModel,
    FlowValidation,
    ModuleDurationEstimate,
)


def launch_workspace(initial_path=None) -> int:
    """Open the unified workspace, preferring the Qt/QML build.

    PySide6 is an optional dependency, so a machine that only has the standard
    library still gets a working workspace: the Tk build is the fallback, not a
    second product.  Both drive the same :mod:`ui.workspace_model`.
    """
    try:
        from .workspace_qt import launch_workspace as launch_qt
    except ImportError:
        import sys

        print(
            "PySide6가 없어 기본(Tk) 워크스페이스로 엽니다. "
            'Qt 화면을 쓰려면 pip install "pne-scheduler[gui]"를 실행하세요.',
            file=sys.stderr,
        )
        from .workspace import launch_workspace as launch_tk

        launch_tk(initial_path)
        return 0
    return launch_qt(initial_path)


def launch_flow_editor(*args, **kwargs):
    from .flow_editor import launch_flow_editor as launch

    return launch(*args, **kwargs)


def launch_project_editor(*args, **kwargs):
    from .project_editor import launch_project_editor as launch

    return launch(*args, **kwargs)


def launch_resume_wizard(*args, **kwargs):
    from .resume_wizard import launch_resume_wizard as launch

    return launch(*args, **kwargs)


def launch_schedule_viewer(*args, **kwargs):
    from .schedule_viewer import launch_schedule_viewer as launch

    return launch(*args, **kwargs)

__all__ = [
    "launch_workspace",
    "launch_flow_editor",
    "FlowProjectModel",
    "FlowDurationEstimate",
    "FlowValidation",
    "ModuleDurationEstimate",
    "launch_project_editor",
    "launch_resume_wizard",
    "launch_schedule_viewer",
]
