"""
core/android_audio.py — Complete Android Audio Subsystem & SoundDevice Drop-In.

Provides:
  - AudioTrack-based playback (streaming RawOutputStream & one-shot play)
  - AudioRecord-based microphone capture (streaming InputStream with callbacks & one-shot record)
  - Full drop-in replacement for `sounddevice` when running on Android or when sounddevice is missing.
  - Safe headless / fallback operation when pyjnius is absent (e.g. during smoke tests or CLI runs).
"""
from __future__ import annotations

import array
import math
import os
import sys
import threading
import time
from typing import Any, Callable, Optional

try:
    import numpy as np
except Exception:
    np = None

_IS_ANDROID_AUDIO = True

# Try to import pyjnius for native Android Media APIs
_HAVE_JNIUS = False
_AudioTrack = None
_AudioRecord = None
_AudioManager = None
_AudioFormat = None

try:
    from jnius import autoclass
    _AudioManager = autoclass("android.media.AudioManager")
    _AudioTrack = autoclass("android.media.AudioTrack")
    _AudioRecord = autoclass("android.media.AudioRecord")
    _AudioFormat = autoclass("android.media.AudioFormat")
    _HAVE_JNIUS = True
except Exception:
    _HAVE_JNIUS = False


# Android Audio Format constants (API 21+)
_STREAM_MUSIC = 3
_STREAM_VOICE_RECOGNITION = 6
_MODE_STREAM = 1
_ENCODING_PCM_16BIT = 2
_CHANNEL_OUT_MONO = 4
_CHANNEL_OUT_STEREO = 12
_CHANNEL_IN_MONO = 16


def is_android() -> bool:
    """Return True if running on an Android system."""
    return _HAVE_JNIUS or "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ


def _get_min_output_buffer(sample_rate: int, channels: int = 1) -> int:
    channel_cfg = _CHANNEL_OUT_MONO if channels == 1 else _CHANNEL_OUT_STEREO
    if _HAVE_JNIUS and _AudioTrack is not None:
        try:
            sz = _AudioTrack.getMinBufferSize(sample_rate, channel_cfg, _ENCODING_PCM_16BIT)
            if sz > 0:
                return sz
        except Exception:
            pass
    return max(4096, sample_rate // 10 * channels * 2)


def _get_min_input_buffer(sample_rate: int, channels: int = 1) -> int:
    channel_cfg = _CHANNEL_IN_MONO if channels == 1 else 12
    if _HAVE_JNIUS and _AudioRecord is not None:
        try:
            sz = _AudioRecord.getMinBufferSize(sample_rate, channel_cfg, _ENCODING_PCM_16BIT)
            if sz > 0:
                return sz
        except Exception:
            pass
    return max(4096, sample_rate // 10 * channels * 2)


# ---------------------------------------------------------------------------
# RawOutputStream: Drop-in replacement for sounddevice.RawOutputStream
# ---------------------------------------------------------------------------
class RawOutputStream:
    """Streams PCM audio to Android AudioTrack (or fallback sink)."""

    def __init__(
        self,
        samplerate: int = 24000,
        channels: int = 1,
        dtype: str = "int16",
        blocksize: int = 1024,
        device: Any = None,
        **kwargs: Any,
    ):
        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self.dtype = dtype
        self.blocksize = int(blocksize) if blocksize else 1024
        self.device = device
        self.latency = 0.05
        self._track = None
        self._is_playing = False
        self._lock = threading.Lock()

    def _init_track(self) -> None:
        if not _HAVE_JNIUS or self._track is not None:
            return
        try:
            channel_cfg = _CHANNEL_OUT_MONO if self.channels == 1 else _CHANNEL_OUT_STEREO
            buf_size = _get_min_output_buffer(self.samplerate, self.channels) * 2
            self._track = _AudioTrack(
                _STREAM_MUSIC,
                self.samplerate,
                channel_cfg,
                _ENCODING_PCM_16BIT,
                buf_size,
                _MODE_STREAM,
            )
        except Exception as e:
            print(f"[AndroidAudio] AudioTrack init failed: {e}")
            self._track = None

    def start(self) -> None:
        with self._lock:
            self._init_track()
            if self._track is not None:
                try:
                    self._track.play()
                except Exception as e:
                    print(f"[AndroidAudio] AudioTrack play failed: {e}")
            self._is_playing = True

    def write(self, data: bytes | bytearray | Any) -> None:
        """Write raw 16-bit PCM samples to the audio track."""
        if np is not None and isinstance(data, np.ndarray):
            raw = data.tobytes()
        else:
            raw = bytes(data)

        if not raw:
            return

        with self._lock:
            if not self._is_playing:
                self.start()

            if self._track is not None:
                try:
                    # AudioTrack.write supports byte[] or short[]
                    # Using short array for maximum compatibility across Android versions
                    short_arr = array.array("h")
                    short_arr.frombytes(raw)
                    # Convert to list or pass directly if pyjnius allows
                    written = self._track.write(short_arr, 0, len(short_arr))
                    if written < 0:
                        print(f"[AndroidAudio] AudioTrack write error: {written}")
                    return
                except Exception as e:
                    print(f"[AndroidAudio] AudioTrack write exception: {e}")

            # Non-Android / fallback timing pacing
            duration = len(raw) / (self.samplerate * self.channels * 2)
            time.sleep(duration * 0.95)

    def stop(self) -> None:
        with self._lock:
            if self._track is not None:
                try:
                    self._track.stop()
                except Exception:
                    pass
            self._is_playing = False

    def close(self) -> None:
        with self._lock:
            self.stop()
            if self._track is not None:
                try:
                    self._track.release()
                except Exception:
                    pass
                self._track = None

    def __enter__(self) -> RawOutputStream:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


OutputStream = RawOutputStream


# ---------------------------------------------------------------------------
# InputStream: Drop-in replacement for sounddevice.InputStream / RawInputStream
# ---------------------------------------------------------------------------
class InputStream:
    """Streams PCM audio from Android AudioRecord with a callback."""

    def __init__(
        self,
        samplerate: int = 16000,
        channels: int = 1,
        dtype: str = "int16",
        blocksize: int = 1024,
        device: Any = None,
        callback: Optional[Callable] = None,
        **kwargs: Any,
    ):
        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self.dtype = dtype
        self.blocksize = int(blocksize) if blocksize else 1024
        self.device = device
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._recorder = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self) -> None:
        recorder = None
        buf_size = _get_min_input_buffer(self.samplerate, self.channels)

        if _HAVE_JNIUS and _AudioRecord is not None:
            try:
                channel_cfg = _CHANNEL_IN_MONO if self.channels == 1 else 12
                recorder = _AudioRecord(
                    _STREAM_VOICE_RECOGNITION,
                    self.samplerate,
                    channel_cfg,
                    _ENCODING_PCM_16BIT,
                    max(buf_size, self.blocksize * 4),
                )
                recorder.startRecording()
                self._recorder = recorder
            except Exception as e:
                print(f"[AndroidAudio] AudioRecord start failed: {e}")
                recorder = None

        samples_per_chunk = self.blocksize
        bytes_per_chunk = samples_per_chunk * 2

        try:
            while self._running:
                t0 = time.time()
                if recorder is not None:
                    try:
                        read_shorts = recorder.read(samples_per_chunk)
                        if isinstance(read_shorts, int):
                            indata = np.zeros(samples_per_chunk, dtype=np.int16) if np is not None else bytes(bytes_per_chunk)
                        else:
                            indata = np.array(read_shorts, dtype=np.int16) if np is not None else bytes(read_shorts)
                    except Exception as e:
                        print(f"[AndroidAudio] Read error: {e}")
                        indata = np.zeros(samples_per_chunk, dtype=np.int16) if np is not None else bytes(bytes_per_chunk)
                else:
                    # Fallback / Simulated silence with low noise floor for testing
                    time.sleep(samples_per_chunk / self.samplerate)
                    indata = np.zeros(samples_per_chunk, dtype=np.int16) if np is not None else bytes(bytes_per_chunk)

                if self.callback:
                    try:
                        self.callback(indata, samples_per_chunk, time.time(), None)
                    except Exception as cb_err:
                        print(f"[AndroidAudio] Callback error: {cb_err}")

        finally:
            if recorder is not None:
                try:
                    recorder.stop()
                    recorder.release()
                except Exception:
                    pass
                self._recorder = None

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def close(self) -> None:
        self.stop()

    def __enter__(self) -> InputStream:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


RawInputStream = InputStream


# ---------------------------------------------------------------------------
# Global One-Shot Audio Playback & Recording
# ---------------------------------------------------------------------------
_global_track_lock = threading.Lock()
_global_active_track = None


def play(samples: Any, samplerate: int = 24000, **kwargs: Any) -> None:
    """Play a numpy array or bytes via AudioTrack."""
    global _global_active_track
    if hasattr(samples, "detach"):
        samples = samples.detach().cpu().numpy()
    if np is not None:
        arr = np.asarray(samples)
        if arr.dtype == np.float32 or arr.dtype == np.float64:
            # Scale float [-1.0, 1.0] to int16 [-32767, 32767]
            arr = np.clip(arr, -1.0, 1.0)
            int16_pcm = (arr * 32767.0).astype(np.int16).tobytes()
        else:
            int16_pcm = arr.astype(np.int16).tobytes()
    else:
        int16_pcm = bytes(samples)

    play_pcm(int16_pcm, sample_rate=samplerate)


def wait() -> None:
    """Wait for current one-shot playback to complete."""
    global _global_active_track
    with _global_track_lock:
        track = _global_active_track
    if track is not None:
        time.sleep(0.05)


def stop() -> None:
    """Stop active playback."""
    global _global_active_track
    with _global_track_lock:
        if _global_active_track is not None:
            try:
                _global_active_track.stop()
                _global_active_track.release()
            except Exception:
                pass
            _global_active_track = None


def play_pcm(pcm_bytes: bytes, sample_rate: int = 24000) -> None:
    """Play raw 16-bit PCM bytes on Android AudioTrack."""
    global _global_active_track
    if not pcm_bytes:
        return

    if _HAVE_JNIUS and _AudioTrack is not None:
        try:
            buf_size = max(_get_min_output_buffer(sample_rate, 1), len(pcm_bytes))
            track = _AudioTrack(
                _STREAM_MUSIC,
                sample_rate,
                _CHANNEL_OUT_MONO,
                _ENCODING_PCM_16BIT,
                buf_size,
                _MODE_STREAM,
            )
            with _global_track_lock:
                _global_active_track = track

            track.play()
            short_arr = array.array("h")
            short_arr.frombytes(pcm_bytes)
            track.write(short_arr, 0, len(short_arr))
            # Wait for playback to finish
            play_dur = len(pcm_bytes) / (sample_rate * 2)
            time.sleep(play_dur + 0.05)
            track.stop()
            track.release()
            with _global_track_lock:
                if _global_active_track == track:
                    _global_active_track = None
            return
        except Exception as e:
            print(f"[AndroidAudio] play_pcm error: {e}")

    # Fallback timing pacing
    time.sleep(len(pcm_bytes) / (sample_rate * 2))


def record_pcm(duration_seconds: float, sample_rate: int = 16000) -> bytes:
    """Record 16-bit PCM from microphone for duration_seconds."""
    total_samples = int(sample_rate * duration_seconds)
    if _HAVE_JNIUS and _AudioRecord is not None:
        try:
            buf_size = _get_min_input_buffer(sample_rate, 1)
            recorder = _AudioRecord(
                _STREAM_VOICE_RECOGNITION,
                sample_rate,
                _CHANNEL_IN_MONO,
                _ENCODING_PCM_16BIT,
                buf_size,
            )
            recorder.startRecording()
            short_arr = array.array("h")
            while len(short_arr) < total_samples:
                chunk = recorder.read(min(buf_size // 2, total_samples - len(short_arr)))
                if isinstance(chunk, int):
                    break
                short_arr.fromlist([int(x) for x in chunk])
            recorder.stop()
            recorder.release()
            return short_arr[:total_samples].tobytes()
        except Exception as e:
            print(f"[AndroidAudio] record_pcm error: {e}")

    # Fallback: return silent PCM
    time.sleep(duration_seconds)
    return bytes(total_samples * 2)


# ---------------------------------------------------------------------------
# Device Query APIs (matching sounddevice device enumeration)
# ---------------------------------------------------------------------------
def query_devices(device: Any = None, kind: Optional[str] = None) -> Any:
    """Return device dictionaries matching sounddevice.query_devices."""
    default_input = {
        "name": "Android Microphone (Default)",
        "hostapi": 0,
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 16000.0,
    }
    default_output = {
        "name": "Android Speaker (Default)",
        "hostapi": 0,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 24000.0,
    }
    devices = [default_input, default_output]

    if device is not None:
        try:
            idx = int(device)
            return devices[idx % len(devices)]
        except Exception:
            return default_input if kind == "input" else default_output

    if kind == "input":
        return default_input
    if kind == "output":
        return default_output

    return devices


def query_hostapis() -> list[dict[str, Any]]:
    """Return host API descriptions matching sounddevice.query_hostapis."""
    return [
        {
            "name": "Android Audio System (AudioTrack/AudioRecord)",
            "devices": [0, 1],
            "default_input_device": 0,
            "default_output_device": 1,
        }
    ]


class _Default:
    device = [0, 1]


default = _Default()
