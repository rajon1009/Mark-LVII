"""
service.py — Android Background Service for Jarvis AI.
Keeps wake-word detection running in the background when phone screen is off or app is minimized.
"""
import os
import sys
import time

print("[JarvisService] Service starting...")

try:
    from core.wake_word import WakeWordDetector

    def on_detected():
        print("[JarvisService] 🔔 Hey Jarvis detected from background service!")
        # If running on Android via pyjnius, launch the main activity
        try:
            from jnius import autoclass
            PythonService = autoclass("org.kivy.android.PythonService")
            service = PythonService.mService
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            context = service.getApplicationContext()
            launch_intent = Intent(context, PythonActivity)
            launch_intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP)
            context.startActivity(launch_intent)
        except Exception as e:
            print(f"[JarvisService] Activity launch error: {e}")

    detector = WakeWordDetector(on_detect=on_detected)
    if detector.ready:
        detector.start()
        print("[JarvisService] Wake-word detector active in background service.")
    else:
        print("[JarvisService] Wake-word model not downloaded yet. Service idling.")
except Exception as e:
    print(f"[JarvisService] Init error: {e}")

# Keep service process alive
while True:
    time.sleep(1.0)
