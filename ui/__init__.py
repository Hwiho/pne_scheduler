"""UI package — visual schedule builder."""

from .flow_model import (
    FlowDurationEstimate,
    FlowProjectModel,
    FlowValidation,
    ModuleDurationEstimate,
)


def launch_workspace(initial_path=None, *, data_dir=None) -> int:
    """Launch the offline Tk client over the shared web application services."""
    import sys
    try:
        from .tk_workspace import launch_workspace as launch
    except ImportError as exc:
        if exc.name not in {"tkinter", "_tkinter"}:
            raise
        print("Tcl/Tk가 포함된 Python을 설치하세요. 웹 서버는 필요하지 않습니다.", file=sys.stderr)
        return 2
    return launch(initial_path, data_dir=data_dir)


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
