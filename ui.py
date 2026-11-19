"""
ui.py — Multi-Platform User Interface for Jarvis AI (Mark LVII).

Supports:
  1. Kivy HUD & Arc Reactor (Android APK & mobile touchscreens)
  2. PyQt6 Desktop HUD (Windows / macOS / Desktop Linux with Qt)
  3. Headless Terminal HUD (Termux CLI / headless test environments)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

_BASE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _BASE_DIR / "config" / "api_keys.json"

# Check available GUI frameworks
_HAVE_QT = False
_HAVE_KIVY = False

if "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ or "--kivy" in sys.argv:
    try:
        import kivy
        _HAVE_KIVY = True
    except Exception:
        _HAVE_KIVY = False
else:
    try:
        from PyQt6.QtWidgets import QApplication
        from gui.window import MainWindow
        _HAVE_QT = True
    except Exception:
        _HAVE_QT = False
        try:
            import kivy
            _HAVE_KIVY = True
        except Exception:
            _HAVE_KIVY = False


def _read_config() -> dict:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_config(data: dict) -> None:
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        current = _read_config()
        current.update(data)
        _CONFIG_PATH.write_text(json.dumps(current, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[UI] Could not save config: {e}")


# ===========================================================================
# 1. Kivy Implementation (Android & Mobile)
# ===========================================================================
if _HAVE_KIVY:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.graphics import Color, Ellipse, Line, Rectangle
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput
    from kivy.uix.widget import Widget

    class ArcReactorWidget(Widget):
        """Custom Iron Man Arc Reactor with rotating rings and audio-reactive center glow."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.audio_level = 0.0
            self.angle = 0.0
            self.state = "LISTENING"
            self.bind(pos=self.redraw, size=self.redraw)
            Clock.schedule_interval(self.update_animation, 1.0 / 30.0)

        def update_animation(self, dt: float) -> None:
            self.angle = (self.angle + 2.5) % 360.0
            self.redraw()

        def redraw(self, *args) -> None:
            self.canvas.clear()
            with self.canvas:
                cx, cy = self.center_x, self.center_y
                r = min(self.width, self.height) * 0.38
                if r <= 10:
                    return

                # State colors
                if self.state == "SPEAKING":
                    c_glow = (0.1, 0.8, 1.0, 0.9)
                    c_ring = (0.0, 0.6, 0.9, 0.5)
                elif self.state == "THINKING":
                    c_glow = (1.0, 0.8, 0.2, 0.9)
                    c_ring = (0.9, 0.7, 0.1, 0.5)
                elif self.state == "LISTENING":
                    c_glow = (0.2, 0.9, 1.0, 0.7)
                    c_ring = (0.1, 0.7, 0.9, 0.4)
                else:
                    c_glow = (0.4, 0.5, 0.6, 0.4)
                    c_ring = (0.3, 0.4, 0.5, 0.3)

                # Outer ring
                Color(*c_ring)
                Line(circle=(cx, cy, r), width=2.5)

                # Segmented middle ring
                Color(c_ring[0], c_ring[1], c_ring[2], 0.7)
                Line(circle=(cx, cy, r * 0.78), width=3.0)

                # Pulsing center reactor core (grows with live voice audio level)
                pulse_r = r * 0.4 + (self.audio_level * r * 0.35)
                Color(*c_glow)
                Ellipse(pos=(cx - pulse_r, cy - pulse_r), size=(pulse_r * 2, pulse_r * 2))

                # Core bright center
                Color(1.0, 1.0, 1.0, 0.95)
                core_inner = pulse_r * 0.45
                Ellipse(pos=(cx - core_inner, cy - core_inner), size=(core_inner * 2, core_inner * 2))

    class JarvisKivyApp(App):
        def __init__(self, ui_controller: Any, **kwargs):
            super().__init__(**kwargs)
            self.ui = ui_controller

        def build(self):
            Window.clearcolor = (0.05, 0.07, 0.1, 1.0)
            root = BoxLayout(orientation="vertical", padding=12, spacing=10)

            # Top Header
            header = BoxLayout(orientation="horizontal", size_hint=(1, 0.08))
            title_lbl = Label(
                text="[b]JARVIS AI — MARK LVII[/b]",
                markup=True,
                color=(0.3, 0.9, 1.0, 1.0),
                font_size="18sp",
                size_hint=(0.7, 1),
            )
            settings_btn = Button(
                text="⚙ SETTINGS",
                size_hint=(0.3, 1),
                background_color=(0.1, 0.3, 0.5, 1.0),
            )
            settings_btn.bind(on_release=lambda *_: self.ui.prompt_reconfig())
            header.add_widget(title_lbl)
            header.add_widget(settings_btn)
            root.add_widget(header)

            # Status Badge
            self.status_lbl = Label(
                text="[b]STATUS: INITIALIZING[/b]",
                markup=True,
                color=(0.2, 0.8, 1.0, 1.0),
                font_size="15sp",
                size_hint=(1, 0.05),
            )
            root.add_widget(self.status_lbl)

            # Center Arc Reactor
            self.reactor = ArcReactorWidget(size_hint=(1, 0.42))
            root.add_widget(self.reactor)

            # Scrollable System Activity Log
            scroll = ScrollView(size_hint=(1, 0.33))
            self.log_lbl = Label(
                text="SYS: Jarvis AI Mark-LVII Initialized.\nSYS: Awaiting activation...",
                color=(0.7, 0.85, 0.95, 1.0),
                font_size="12sp",
                size_hint_y=None,
                halign="left",
                valign="top",
            )
            self.log_lbl.bind(
                texture_size=lambda *_: setattr(self.log_lbl, "height", self.log_lbl.texture_size[1])
            )
            self.log_lbl.bind(width=lambda *_: setattr(self.log_lbl, "text_size", (self.log_lbl.width, None)))
            scroll.add_widget(self.log_lbl)
            root.add_widget(scroll)

            # Bottom Command Bar
            bottom = BoxLayout(orientation="horizontal", size_hint=(1, 0.12), spacing=8)
            self.cmd_input = TextInput(
                hint_text="Ask Jarvis or type command...",
                multiline=False,
                size_hint=(0.65, 1),
                background_color=(0.1, 0.15, 0.22, 1.0),
                foreground_color=(1, 1, 1, 1),
            )
            self.cmd_input.bind(on_text_validate=lambda *_: self._send_command())

            send_btn = Button(
                text="SEND",
                size_hint=(0.18, 1),
                background_color=(0.0, 0.5, 0.8, 1.0),
            )
            send_btn.bind(on_release=lambda *_: self._send_command())

            self.mic_btn = Button(
                text="🎤 MIC",
                size_hint=(0.17, 1),
                background_color=(0.2, 0.7, 0.4, 1.0),
            )
            self.mic_btn.bind(on_release=lambda *_: self._toggle_mic())

            bottom.add_widget(self.cmd_input)
            bottom.add_widget(send_btn)
            bottom.add_widget(self.mic_btn)
            root.add_widget(bottom)

            # Check if API key is missing -> automatically show runtime entry dialog
            Clock.schedule_once(lambda *_: self._check_api_key_on_launch(), 0.5)

            return root

        def _send_command(self) -> None:
            txt = self.cmd_input.text.strip()
            if txt and self.ui.on_text_command:
                self.cmd_input.text = ""
                self.ui.write_log(f"USER: {txt}")
                threading.Thread(target=self.ui.on_text_command, args=(txt,), daemon=True).start()

        def _toggle_mic(self) -> None:
            self.ui.muted = not self.ui.muted
            if self.ui.muted:
                self.mic_btn.text = "🔇 MUTED"
                self.mic_btn.background_color = (0.7, 0.2, 0.2, 1.0)
            else:
                self.mic_btn.text = "🎤 MIC"
                self.mic_btn.background_color = (0.2, 0.7, 0.4, 1.0)

        def _check_api_key_on_launch(self) -> None:
            cfg = _read_config()
            key = str(cfg.get("gemini_api_key", "")).strip()
            if not key:
                self.ui.prompt_reconfig()
            else:
                self.ui._ready = True

    class _KivyRootShim:
        def __init__(self, app: JarvisKivyApp):
            self.app = app

        def mainloop(self):
            self.app.run()


# ===========================================================================
# 2. Main JarvisUI Controller Interface
# ===========================================================================
class JarvisUI:
    """Unified JarvisUI interface that works across Android (Kivy), Desktop (Qt), and CLI."""

    def __init__(self, face_path: str = "face.png", size: Any = None):
        self._ready = False
        self._muted = False
        self._assistant_name = "JARVIS"

        # Callbacks expected by main.py
        self.on_text_command: Optional[Callable[[str], None]] = None
        self.on_push_to_talk: Optional[Callable[[bool], None]] = None
        self.ptt_hold: Optional[Callable[[bool], None]] = None
        self.on_remote_clicked: Optional[Callable[[], None]] = None
        self.on_interrupt: Optional[Callable[[], None]] = None
        self.on_voice_change: Optional[Callable[[str], None]] = None
        self.on_audio_device_change: Optional[Callable[[str], None]] = None

        self.get_plugins: Optional[Callable] = None
        self.get_plugin_settings: Optional[Callable] = None
        self.request_say: Optional[Callable] = None
        self.tool_catalog: Optional[Callable] = None
        self.run_tool: Optional[Callable] = None
        self.wake_is_ready: Optional[Callable[[], bool]] = None
        self.wake_get_state: Optional[Callable[[], dict]] = None
        self.on_wake_toggle: Optional[Callable[[bool], str]] = None
        self.on_wake_manual: Optional[Callable[[], None]] = None
        self.on_wake_install: Optional[Callable[[], tuple[bool, str]]] = None

        self._active_backend = "headless"
        self._kivy_app: Optional[JarvisKivyApp] = None
        self._qt_win = None

        # Check existing API key
        cfg = _read_config()
        if str(cfg.get("gemini_api_key", "")).strip():
            self._ready = True

        if _HAVE_QT:
            try:
                self._app = QApplication.instance() or QApplication(sys.argv)
                self._win = MainWindow(face_path)
                self.root = type("RootShim", (), {"mainloop": self._win.show and self._app.exec})()
                self._qt_win = self._win
                self._active_backend = "qt"
                return
            except Exception as e:
                print(f"[UI] Qt init failed: {e} — falling back")

        if _HAVE_KIVY:
            try:
                self._kivy_app = JarvisKivyApp(self)
                self.root = _KivyRootShim(self._kivy_app)
                self._active_backend = "kivy"
                return
            except Exception as e:
                print(f"[UI] Kivy init failed: {e} — falling back to CLI")

        # Headless CLI Fallback
        self._active_backend = "headless"
        self.root = type("CliRoot", (), {"mainloop": self._cli_mainloop})()

    @property
    def muted(self) -> bool:
        return self._muted

    @muted.setter
    def muted(self, v: bool):
        self._muted = bool(v)
        if self._qt_win and hasattr(self._qt_win, "_muted"):
            self._qt_win._muted = self._muted

    @property
    def current_file(self) -> str | None:
        return None

    @property
    def assistant_name(self) -> str:
        return self._assistant_name

    def wait_for_api_key(self) -> None:
        """Blocks runner thread until user enters API key in UI."""
        while not self._ready:
            time.sleep(0.2)

    def write_log(self, text: str) -> None:
        print(f"[JARVIS LOG] {text}")
        if self._qt_win:
            try:
                self._qt_win._log_sig.emit(str(text))
            except Exception:
                pass
        elif self._kivy_app and hasattr(self._kivy_app, "log_lbl"):
            def _update(*_):
                curr = self._kivy_app.log_lbl.text
                lines = curr.splitlines()[-25:]
                lines.append(f"{time.strftime('%H:%M:%S')} {text}")
                self._kivy_app.log_lbl.text = "\n".join(lines)
            Clock.schedule_once(_update, 0)

    def set_state(self, state: str) -> None:
        state_str = str(state).upper()
        if self._qt_win:
            try:
                self._qt_win._state_sig.emit(state_str)
            except Exception:
                pass
        elif self._kivy_app and hasattr(self._kivy_app, "status_lbl"):
            def _update(*_):
                self._kivy_app.status_lbl.text = f"[b]STATUS: {state_str}[/b]"
                if hasattr(self._kivy_app, "reactor"):
                    self._kivy_app.reactor.state = state_str
            Clock.schedule_once(_update, 0)

    def set_audio_level(self, level: float) -> None:
        lvl = max(0.0, min(1.0, float(level)))
        if self._qt_win:
            try:
                self._qt_win.hud.set_audio_level(lvl)
            except Exception:
                pass
        elif self._kivy_app and hasattr(self._kivy_app, "reactor"):
            self._kivy_app.reactor.audio_level = lvl

    def push_visemes(self, frames: Any, hop: float, at: float) -> None:
        pass

    def glance(self, dx: float, dy: float, hold: float = 1.1) -> None:
        pass

    def start_speaking(self) -> None:
        self.set_state("SPEAKING")

    def stop_speaking(self) -> None:
        if not self.muted:
            self.set_state("LISTENING")

    def prompt_reconfig(self) -> None:
        """Displays modal API key entry interface."""
        if self._active_backend == "kivy" and _HAVE_KIVY:
            def _show_modal(*_):
                box = BoxLayout(orientation="vertical", padding=15, spacing=10)
                box.add_widget(
                    Label(
                        text="[b]Enter Gemini API Key:[/b]",
                        markup=True,
                        font_size="16sp",
                        size_hint=(1, 0.25),
                    )
                )

                cfg = _read_config()
                txt_input = TextInput(
                    text=cfg.get("gemini_api_key", ""),
                    multiline=False,
                    password=True,
                    size_hint=(1, 0.35),
                    background_color=(0.1, 0.15, 0.2, 1),
                    foreground_color=(1, 1, 1, 1),
                )
                box.add_widget(txt_input)

                btn_box = BoxLayout(orientation="horizontal", spacing=10, size_hint=(1, 0.4))
                save_btn = Button(text="CONNECT", background_color=(0.1, 0.7, 0.3, 1))
                popup = Popup(
                    title="Jarvis API Setup",
                    content=box,
                    size_hint=(0.85, 0.45),
                    auto_dismiss=False,
                )

                def _save(*_):
                    k = txt_input.text.strip()
                    if k:
                        _save_config({"gemini_api_key": k})
                        self._ready = True
                        popup.dismiss()
                        self.write_log("SYS: Gemini API Key saved. Jarvis connecting...")

                save_btn.bind(on_release=_save)
                btn_box.add_widget(save_btn)
                box.add_widget(btn_box)
                popup.open()

            Clock.schedule_once(_show_modal, 0)
        elif self._active_backend == "qt":
            try:
                self._qt_win.prompt_reconfig()
            except Exception:
                pass
        else:
            # Headless CLI
            print("\n" + "=" * 50)
            print("  JARVIS AI — API KEY SETUP")
            print("=" * 50)
            try:
                k = input("Please enter your Gemini API Key: ").strip()
                if k:
                    _save_config({"gemini_api_key": k})
                    self._ready = True
                    print("✅ API Key configured successfully.")
            except Exception:
                pass

    def show_content(self, title: str, text: str) -> None:
        self.write_log(f"[{title}] {text[:200]}")

    def show_code_job(self, job: dict) -> None:
        self.write_log(f"[CODE JOB] {job.get('action', 'running')}...")

    def show_quiz(self, topic: str, questions: Any, grade: Any = None) -> None:
        pass

    def hide_quiz(self) -> None:
        pass

    def show_review(self, title: str, summary: str, findings: Any, unclear: Any = None) -> None:
        pass

    def show_confirm(self, title: str, detail: str) -> None:
        self.write_log(f"[CONFIRM NEEDED] {title}: {detail}")

    def hide_confirm(self) -> None:
        pass

    def show_camera_frame(self, img_bytes: bytes) -> None:
        pass

    def show_video(self, source: str, title: str = "", muted: bool = True, audio_source: str = "") -> None:
        pass

    def show_image(self, path: str, title: str = "") -> None:
        pass

    def stop_video(self) -> None:
        pass

    def set_video_muted(self, muted: bool) -> None:
        pass

    def video_is_playing(self) -> bool:
        return False

    def seek_video(self, seconds: float, relative: bool = True) -> None:
        pass

    def pause_video(self, paused: bool = True) -> None:
        pass

    def video_state(self) -> dict:
        return {}

    def start_camera_stream(self) -> None:
        pass

    def stop_camera_stream(self) -> None:
        pass

    def notify_phone_connected(self) -> None:
        self.write_log("SYS: Device connected.")

    def _cli_mainloop(self) -> None:
        """Terminal interactive loop for Termux CLI / testing."""
        print("[JARVIS] Running in interactive terminal mode. Type commands below (or 'exit' to quit):")
        while True:
            try:
                cmd = input("Jarvis > ").strip()
                if not cmd:
                    continue
                if cmd.lower() in ("exit", "quit", "shutdown"):
                    break
                if self.on_text_command:
                    self.on_text_command(cmd)
            except (KeyboardInterrupt, EOFError):
                break