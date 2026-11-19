"""Android runtime permissions.

Declaring a permission in ``buildozer.spec`` only writes it into the manifest.
From Android 6 on the dangerous ones are also granted by the user at runtime,
and an app that never asks fails silently: ``AudioRecord.startRecording()``
throws, the camera returns nothing, and from API 33 a foreground service cannot
post its (mandatory) notification.

``ensure()`` asks once at startup and waits, with a deadline, for the answer.
The microphone stream opens seconds later on a worker thread and cannot show a
dialog itself, so the answer has to be known before it starts.

Off Android — and whenever the p4a ``android`` module is missing — every call
here is a no-op. Nothing in this module raises.
"""
from __future__ import annotations

import os
import threading
from typing import Iterable, Optional

# The voice session is the whole app, so the microphone comes first. Camera is
# used by the vision tools; notifications by the foreground wake-word service.
DEFAULT_PERMISSIONS = (
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.POST_NOTIFICATIONS",
)


def is_android() -> bool:
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ


def _on_ui_thread(fn) -> None:
    """Run ``fn`` on the UI thread when Kivy's event loop is available.

    ``Activity.requestPermissions`` belongs on the UI thread, and Kivy's Clock
    is the only handle a worker thread has on it. Without Kivy (tests, desktop)
    the call is made directly.
    """
    try:
        from kivy.clock import Clock

        Clock.schedule_once(lambda *_: fn(), 0)
    except Exception:
        fn()


def ensure(
    permissions: Optional[Iterable[str]] = None,
    timeout: float = 30.0,
    logger=print,
) -> dict[str, bool]:
    """Request the missing permissions and wait for the user's answer.

    Returns ``{permission: granted}`` for everything asked for. Returns ``{}``
    off Android or when the ``android`` module is unavailable.
    """
    if not is_android():
        return {}

    wanted = list(permissions or DEFAULT_PERMISSIONS)
    try:
        from android.permissions import check_permission, request_permissions
    except Exception as e:
        logger(f"[permissions] android module unavailable: {e}")
        return {}

    try:
        missing = [p for p in wanted if not check_permission(p)]
    except Exception as e:
        logger(f"[permissions] could not read permission state: {e}")
        return {}

    if not missing:
        return {p: True for p in wanted}

    done = threading.Event()
    result: dict[str, bool] = {}

    def _callback(granted_permissions, grants) -> None:
        for perm, ok in zip(granted_permissions, grants):
            result[perm] = bool(ok)
        done.set()

    def _ask() -> None:
        try:
            request_permissions(missing, _callback)
        except Exception as e:
            logger(f"[permissions] request failed: {e}")
            done.set()

    names = ", ".join(p.rsplit(".", 1)[-1] for p in missing)
    logger(f"[permissions] asking for: {names}")
    _on_ui_thread(_ask)
    done.wait(timeout)

    # The callback is authoritative, but a request that was interrupted can
    # arrive with an empty list — re-read the real state in that case.
    granted: dict[str, bool] = {}
    for perm in wanted:
        try:
            granted[perm] = bool(check_permission(perm))
        except Exception:
            granted[perm] = bool(result.get(perm, False))

    denied = [p.rsplit(".", 1)[-1] for p, ok in granted.items() if not ok]
    if denied:
        logger(f"[permissions] not granted: {', '.join(denied)}")
    return granted
