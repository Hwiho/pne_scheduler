"""UI package — visual schedule builder."""

from .flow_model import (
    FlowDurationEstimate,
    FlowProjectModel,
    FlowValidation,
    ModuleDurationEstimate,
)


def launch_workspace(initial_path=None) -> int:
    """Point the user at the web workspace.

    The Tk and Qt shells were removed in Gate G4: maintaining two of them was
    already producing features that existed in only one. The workspace is now
    `web/` over `api/`, which is two processes rather than one import, so this
    says how to start them instead of pretending it can.
    """
    import sys

    print(
        "워크스페이스는 웹으로 옮겨졌습니다.\n"
        "  1) python run_pne_scheduler_api.py\n"
        "  2) cd web && npm run dev   → http://localhost:3000",
        file=sys.stderr,
    )
    if initial_path is not None:
        print(f"열려던 파일: {initial_path}", file=sys.stderr)
    return 2


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
