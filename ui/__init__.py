"""UI package — visual schedule builder."""

from .flow_model import FlowProjectModel, FlowValidation


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
    "launch_flow_editor",
    "FlowProjectModel",
    "FlowValidation",
    "launch_project_editor",
    "launch_resume_wizard",
    "launch_schedule_viewer",
]
