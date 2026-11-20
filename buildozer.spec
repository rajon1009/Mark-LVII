[app]

# (str) Title of your application
title = Jarvis AI

# (str) Package name
package.name = jarvisai

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Application versioning (must be set; otherwise buildozer refuses to build)
version = 1.0

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
# md  -> agents/*.md (task-engine profiles)
# obj -> core/face_model.obj (avatar mesh)
# html/js -> dashboard/static (phone dashboard)
source.include_exts = py,png,jpg,kv,ttf,otf,json,zip,txt,ico,md,obj,html,js,css

# (list) List of inclusions using pattern matching
source.include_patterns = assets/*,core/*,config/*,memory/*,actions/*,dashboard/*,agents/*,gui/*,plugins/*,providers/*

# (list) Folders to skip when copying the source tree
source.exclude_dirs = bin,.buildozer,dist,build,venv,__pycache__,.github
# exclude_dirs only matches paths from the root, so nested __pycache__ needs a pattern
source.exclude_patterns = */__pycache__/*

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
# scipy was listed but nothing in the project imports it; its recipe is slow and
# a common build failure on p4a, so it is not part of the APK.
requirements = python3,kivy,pyjnius,requests,certifi,pillow,edge-tts,google-genai,httpx,websockets,fastapi,uvicorn,numpy,psutil

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 1

# (list) Permissions
# POST_NOTIFICATIONS is required from API 33 on: the foreground service cannot
# show its (mandatory) notification without it.
android.permissions = RECORD_AUDIO, MODIFY_AUDIO_SETTINGS, INTERNET, ACCESS_NETWORK_STATE, WAKE_LOCK, FOREGROUND_SERVICE, FOREGROUND_SERVICE_MICROPHONE, POST_NOTIFICATIONS, CAMERA, SET_WALLPAPER, VIBRATE

# (bool) Accept the Android SDK licence automatically (required for CI builds;
# without it buildozer waits on an interactive prompt and the job dies)
android.accept_sdk_license = True

# (int) Target Android API, should be as high as possible.
# 35 = Android 15, what p4a v2026.05 and AGP 8.11 expect. It is also the first
# target where the microphone foreground service must declare its type.
android.api = 35

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# android.sdk / android.ndk are deliberately not set: buildozer then uses the
# versions the pinned p4a release recommends (NDK 28c for p4a 2026.05). A stale
# 25b here is what makes a modern p4a fail at the first recipe.

# (str) python-for-android revision. Pinning the release keeps CI reproducible;
# master moves and has broken builds before. This release adds the recipes this
# app needs (pydantic-core, httpx, vosk, grpcio).
p4a.branch = v2026.05.09

# (bool) Use --private data storage (True) or --dir public storage (False)
android.private_storage = True

# (bool) Android logcat filters to use
android.logcat_filters = *:S python:D

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (list) Android service to declare
# foregroundServiceType=microphone is mandatory from Android 14 on; without it
# startForeground() throws MissingForegroundServiceTypeException and the
# wake-word service dies. Syntax added in p4a v2026.05.
services = JarvisService:service.py:foreground:foregroundServiceType=microphone

# (bool) Enable Android hardware acceleration
android.hw_accel = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
