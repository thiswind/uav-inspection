"""Optional URL prefix for reverse-proxy sub-path deployments.

Set UAV_URL_PREFIX (e.g. "/uav") when the app is served behind a gateway that
strips the prefix before proxying. URLs embedded in JSON responses are then
returned with the prefix so browsers can fetch them directly. Default empty
keeps the original root-path behaviour.
"""
from __future__ import annotations

import os

_PREFIX = os.environ.get("UAV_URL_PREFIX", "").strip()
if _PREFIX and not _PREFIX.startswith("/"):
    _PREFIX = "/" + _PREFIX
_PREFIX = _PREFIX.rstrip("/")


def prefixed(path: str) -> str:
    """Prepend the deployment prefix to a root-absolute app path."""
    if not _PREFIX or not path.startswith("/"):
        return path
    return _PREFIX + path
