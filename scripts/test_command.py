import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_SECRET_KEY"] = "verification-key"

import django
from django.conf import settings

settings.DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

django.setup()

from django.core.management import call_command

print("Testing migrate...")
call_command("migrate", "--verbosity=0")

print("Testing load_initial_data command...")
call_command("load_initial_data")

print("Testing second run of load_initial_data (should skip without error)...")
call_command("load_initial_data")

