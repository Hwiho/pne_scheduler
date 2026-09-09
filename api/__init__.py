"""HTTP surface over :mod:`ui.workspace_model`.

The rule this package exists to hold: **the model decides, the API reports.**
Every gate — what may be exported, whether a file is equipment-executable, which
patterns are trusted — is computed in `release.py` and `validate/`, and travels
outward as data. Nothing here recomputes a decision, and no client is ever asked
to make one.

Three of the four route groups are stateless: the caller sends the whole project,
the server builds a detached document, acts once, and returns the result. That is
possible because `ScheduleProject` round-trips through `to_dict`/`from_dict`, and
it means the server holds no session, survives restart, and stays testable as
plain functions.

The fourth group — library, import session, export — touches the filesystem. It
is the boundary to hold if any of this is ever centralised.
"""

from .app import create_app

__all__ = ["create_app"]
