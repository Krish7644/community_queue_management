import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))

# Point Django to a temporary sqlite database in memory or local test db
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_SECRET_KEY"] = "verification-key"

import django
from django.conf import settings

# Override DATABASES with SQLite for testing fixture validity
settings.DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

django.setup()

from django.core.management import call_command

print("1. Running migrate on test database...")
call_command("migrate", "--verbosity=0")

print("2. Loading fixture initial_data.json...")
call_command("loaddata", "initial_data.json", "--verbosity=1")

from portal.models import Authority, CombinedPass, Member, User
print("\n--- Verification stats in test DB ---")
print(f"Users: {User.objects.count()}")
print(f"Authorities: {Authority.objects.count()}")
print(f"Combined passes: {CombinedPass.objects.count()}")
print(f"Members: {Member.objects.count()}")
print("All data verified and successfully loaded via Django ORM!")

