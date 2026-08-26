"""
Local OS notifications (Windows) – sound + desktop balloon.

Called from process_alert so alerts are noticeable even when the browser
tab is in the background or another page is open.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)
_last_siren_ts = 0.0
_siren_lock = threading.Lock()


def _play_windows_siren(seconds: float = 5.0) -> None:
    """Blocking siren using winsound (Windows only)."""
    try:
        import winsound
        end = time.time() + max(1.0, float(seconds))
        # Alternating beeps ~5s
        while time.time() < end:
            winsound.Beep(900, 280)
            if time.time() >= end:
                break
            winsound.Beep(1400, 280)
    except Exception as exc:
        logger.warning("winsound siren failed: %s", exc)
        try:
            # Fallback system sound
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass


def _windows_balloon(title: str, message: str, ms: int = 8000) -> None:
    """Show a Windows tray balloon tip (visible outside the browser)."""
    if sys.platform != "win32":
        return
    # Escape for PowerShell single-quoted strings
    def _ps(s: str) -> str:
        return (s or "").replace("'", "''")[:180]

    title_ps = _ps(title)
    msg_ps = _ps(message)
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Error
$n.Visible = $true
$n.BalloonTipTitle = '{title_ps}'
$n.BalloonTipText = '{msg_ps}'
$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Error
$n.ShowBalloonTip({int(ms)})
Start-Sleep -Milliseconds {int(ms) + 400}
$n.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as exc:
        logger.warning("Windows balloon failed: %s", exc)


def notify_local_attack(
    title: str,
    message: str,
    *,
    play_sound: bool = True,
    show_balloon: bool = True,
    sound_seconds: float = 5.0,
) -> None:
    """
    Fire local sound + desktop balloon in background threads.

    Safe to call from alert pipeline / Streamlit / API.
    """
    title = (title or "AI-NDR Attack Alert").strip()
    message = (message or "Attack detected").strip()

    if show_balloon:
        try:
            threading.Thread(
                target=_windows_balloon,
                args=(title, message, 8000),
                daemon=True,
            ).start()
        except Exception as exc:
            logger.warning("balloon thread failed: %s", exc)

    if play_sound and sys.platform == "win32":
        # Immediate short beep (sync) so user hears something even if thread is delayed
        try:
            import winsound
            winsound.Beep(1100, 350)
        except Exception:
            pass
        try:
            threading.Thread(
                target=_play_windows_siren,
                args=(sound_seconds,),
                daemon=True,
            ).start()
        except Exception as exc:
            logger.warning("sound thread failed: %s", exc)


def notify_from_alert_fields(
    severity: str,
    label: str,
    source_ip: str = "",
) -> None:
    """Convenience wrapper used by process_alert (siren debounced ~4.5s)."""
    global _last_siren_ts
    title = f"AI-NDR [{severity}] {label}"
    body = f"{label} detected"
    if source_ip:
        body += f" from {source_ip}"
    play = True
    with _siren_lock:
        now = time.time()
        if now - _last_siren_ts < 4.5:
            play = False
        else:
            _last_siren_ts = now
    notify_local_attack(title, body, play_sound=play, show_balloon=True, sound_seconds=5.0)
