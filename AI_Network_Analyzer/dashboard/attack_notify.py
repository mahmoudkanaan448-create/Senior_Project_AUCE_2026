"""
Global attack notifications across all dashboard pages.

Strategy:
1) pending_global_notify queue → fires on ANY page after navigation
2) last_alert_id watermark → detects new DB alerts while browsing
3) Browser toast/banner + optional WebAudio
4) Windows sound/balloon are triggered from process_alert (backend)
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from dashboard.i18n import t


def _sound_enabled() -> bool:
    if "attack_sound_enabled" in st.session_state:
        return bool(st.session_state.attack_sound_enabled)
    try:
        from database.database import SessionLocal
        from database import queries
        db = SessionLocal()
        try:
            val = queries.get_setting(db, "attack_sound_enabled")
            enabled = (val or "1") not in ("0", "false", "False", "no")
        finally:
            db.close()
    except Exception:
        enabled = True
    st.session_state.attack_sound_enabled = enabled
    return enabled


def play_attack_sound(times: int = 8) -> None:
    """Browser siren (~5s). Also kicks a short Windows beep as fallback."""
    if not _sound_enabled():
        return
    # Windows beep immediately (works even if JS audio is blocked)
    try:
        from alerts.local_notify import notify_local_attack
        notify_local_attack(
            "AI-NDR Attack",
            "Attack alert",
            play_sound=True,
            show_balloon=False,
            sound_seconds=5.0,
        )
    except Exception:
        pass

    components.html(
        """
        <script>
        (function() {
          try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            const ctx = new AudioCtx();
            if (ctx.state === 'suspended') { ctx.resume(); }
            const master = ctx.createGain();
            master.gain.value = 0.75;
            master.connect(ctx.destination);
            const duration = 5.0;
            const start = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(650, start);
            for (let i = 0; i < 10; i++) {
              const t = start + i * 0.5;
              osc.frequency.linearRampToValueAtTime(i % 2 === 0 ? 1500 : 650, t + 0.5);
            }
            gain.gain.setValueAtTime(0.0001, start);
            gain.gain.exponentialRampToValueAtTime(0.85, start + 0.05);
            gain.gain.setValueAtTime(0.85, start + duration - 0.25);
            gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
            osc.connect(gain); gain.connect(master);
            osc.start(start); osc.stop(start + duration);
            setTimeout(() => { try { ctx.close(); } catch (e) {} }, 5600);
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def fire_desktop_notification(title: str, body: str) -> None:
    safe_title = json.dumps(str(title)[:80])
    safe_body = json.dumps(str(body)[:180])
    components.html(
        f"""
        <script>
        (function() {{
          const title = {safe_title};
          const body = {safe_body};
          function show() {{
            try {{
              new Notification(title, {{ body: body, requireInteraction: true, tag: 'aindr-' + Date.now() }});
            }} catch (e) {{}}
          }}
          if (!('Notification' in window)) return;
          if (Notification.permission === 'granted') show();
          else if (Notification.permission !== 'denied') {{
            Notification.requestPermission().then(function(p) {{ if (p === 'granted') show(); }});
          }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def show_attack_toast(title: str, message: str, icon: str = "🚨") -> None:
    try:
        st.toast(f"{icon} {title}: {message}", icon="🚨", duration=5)
    except TypeError:
        try:
            st.toast(f"{icon} {title}: {message}", icon="🚨")
        except Exception:
            st.warning(f"{icon} **{title}** — {message}")
    except Exception:
        st.warning(f"{icon} **{title}** — {message}")


def show_attack_banner(alerts: List[Dict[str, Any]], seconds: int = 5) -> None:
    if not alerts:
        return
    top = alerts[0]
    extra = f" · +{len(alerts) - 1} more" if len(alerts) > 1 else ""
    priority = top.get("priority", "High")
    atype = top.get("type", "Attack")
    msg = (top.get("message") or "")[:160].replace("`", "'").replace("<", "").replace(">", "")
    sec = max(1, int(seconds))
    # Visible markdown banner (more reliable than iframe-only)
    st.error(f"**ATTACK ALERT{extra}** — [{priority}] {atype}: {msg}")
    components.html(
        f"""
        <div id="aindr-attack-banner" style="
            position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:99999;
            width:min(920px,94vw);background:linear-gradient(90deg,#7f1d1d,#b45309);
            border:2px solid #fbbf24;border-radius:14px;padding:16px 20px;
            box-shadow:0 0 28px rgba(251,191,36,0.45);font-family:Segoe UI,Arial,sans-serif;">
          <div style="color:#fff;font-size:20px;font-weight:800;">ATTACK ALERT{extra}</div>
          <div style="color:#fef3c7;font-size:15px;font-weight:650;margin-top:6px;">
            [{priority}] {atype} — {msg}
          </div>
        </div>
        <script>
        setTimeout(function(){{
          var el=document.getElementById('aindr-attack-banner');
          if(el){{ el.style.opacity='0'; setTimeout(function(){{ el.remove(); }},400); }}
        }}, {sec * 1000});
        </script>
        """,
        height=1,
    )


def queue_global_notify(
    title: str,
    message: str,
    severity: str = "High",
    source_ip: str = "",
) -> None:
    """Queue a notification that will fire on the current OR next page load."""
    st.session_state["pending_global_notify"] = {
        "title": title,
        "message": message,
        "severity": severity,
        "source_ip": source_ip,
    }


def notify_attack_event(
    label: str,
    severity: str = "High",
    source_ip: str = "",
    play_sound: bool = True,
) -> None:
    """Immediate UI notify + queue for other pages."""
    msg = f"{label}" + (f" from {source_ip}" if source_ip else "")
    title = f"{severity} Attack Detected"
    queue_global_notify(title, msg, severity=severity, source_ip=source_ip)
    show_attack_toast(title, msg)
    show_attack_banner([{"priority": severity, "type": label, "message": msg}], seconds=5)
    fire_desktop_notification(f"AI-NDR {title}", msg)
    if play_sound:
        play_attack_sound(8)
    try:
        from alerts.local_notify import notify_local_attack
        notify_local_attack(f"AI-NDR {title}", msg, play_sound=True, show_balloon=True, sound_seconds=5.0)
    except Exception:
        pass


def _latest_alert_snapshot() -> Dict[str, Any]:
    """Return {max_id, alerts[]} for New Medium+ alerts."""
    try:
        from database.database import SessionLocal
        from database.models import Alert
        db = SessionLocal()
        try:
            rows = (
                db.query(Alert)
                .filter(Alert.status == "New")
                .filter(Alert.priority.in_(["Medium", "High", "Critical"]))
                .order_by(Alert.alert_id.desc())
                .limit(15)
                .all()
            )
            alerts = [
                {
                    "id": a.alert_id,
                    "type": a.alert_type or "Attack",
                    "priority": a.priority or "High",
                    "message": a.message or "",
                }
                for a in rows
            ]
            max_id = alerts[0]["id"] if alerts else 0
            return {"max_id": max_id, "alerts": alerts}
        finally:
            db.close()
    except Exception:
        return {"max_id": 0, "alerts": []}


def _flush_pending() -> None:
    pending = st.session_state.pop("pending_global_notify", None)
    if not pending:
        return
    title = pending.get("title") or "Attack Detected"
    message = pending.get("message") or "New attack"
    severity = pending.get("severity") or "High"
    show_attack_toast(title, message)
    show_attack_banner(
        [{"priority": severity, "type": title, "message": message}],
        seconds=5,
    )
    fire_desktop_notification(f"AI-NDR {title}", message)
    play_attack_sound(8)
    try:
        from alerts.local_notify import notify_local_attack
        notify_local_attack(f"AI-NDR {title}", message, play_sound=True, show_balloon=True, sound_seconds=5.0)
    except Exception:
        pass
    # Mark current alerts as consumed so Home doesn't double-fire from watermark
    try:
        snap = _latest_alert_snapshot()
        st.session_state.alert_watermark = int(snap.get("max_id") or 0)
    except Exception:
        pass


def render_attack_notifier() -> None:
    """Mount on every authenticated page via gate_page()."""
    if "alert_watermark" not in st.session_state:
        st.session_state.alert_watermark = None  # None = not initialized

    with st.sidebar:
        st.markdown(f"### {t('notify.alerts')}")
        sound_on = st.checkbox(
            t("notify.sound"),
            value=_sound_enabled(),
            key="toggle_attack_sound",
        )
        st.session_state.attack_sound_enabled = sound_on
        if st.button(t("notify.enable"), use_container_width=True, type="primary", key="enable_alerts_btn"):
            st.session_state.attack_sound_unlocked = True
            components.html(
                """
                <script>
                if ('Notification' in window && Notification.permission !== 'granted') {
                  Notification.requestPermission();
                }
                </script>
                """,
                height=0,
                width=0,
            )
            try:
                from alerts.local_notify import notify_local_attack
                notify_local_attack(
                    "AI-NDR Ready",
                    "Sound and desktop alerts enabled",
                    play_sound=True,
                    show_balloon=True,
                    sound_seconds=2.0,
                )
            except Exception:
                pass
            play_attack_sound(8)
            st.success(t("notify.enabled"))

    # 1) Fire anything queued from another page (Threat Simulation → Home)
    _flush_pending()

    # 2) Watermark-based detection of brand-new alerts
    snap = _latest_alert_snapshot()
    max_id = int(snap.get("max_id") or 0)
    alerts = snap.get("alerts") or []

    if st.session_state.alert_watermark is None:
        # First page in session: remember current max, don't alarm historical
        st.session_state.alert_watermark = max_id
    else:
        prev = int(st.session_state.alert_watermark or 0)
        if max_id > prev:
            newest = [a for a in alerts if int(a["id"]) > prev]
            if newest:
                top = newest[0]
                notify_attack_event(
                    label=str(top.get("type") or "Attack"),
                    severity=str(top.get("priority") or "High"),
                    source_ip="",
                    play_sound=True,
                )
            st.session_state.alert_watermark = max_id
            # Clear pending since we just notified
            st.session_state.pop("pending_global_notify", None)

    # 3) Keep polling while user stays on a page
    try:
        @st.fragment(run_every=timedelta(seconds=3))
        def _watch():
            s = _latest_alert_snapshot()
            mid = int(s.get("max_id") or 0)
            prev = int(st.session_state.get("alert_watermark") or 0)
            if mid > prev:
                newest = [a for a in (s.get("alerts") or []) if int(a["id"]) > prev]
                if newest:
                    top = newest[0]
                    show_attack_toast(
                        f"{top.get('priority')} Attack",
                        f"{top.get('type')} — {(top.get('message') or '')[:80]}",
                    )
                    show_attack_banner(newest, seconds=5)
                    fire_desktop_notification(
                        f"AI-NDR {top.get('priority')} Attack",
                        f"{top.get('type')}: {(top.get('message') or '')[:120]}",
                    )
                    play_attack_sound(8)
                st.session_state.alert_watermark = mid

        _watch()
    except Exception:
        pass
