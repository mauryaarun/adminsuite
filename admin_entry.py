# admin_entry.py

import os

# Helpful for PyInstaller / QtWebEngine packaged builds.
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

from admin_suite.app import main

if __name__ == "__main__":
    raise SystemExit(main())
