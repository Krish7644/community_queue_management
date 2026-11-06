import os
import sys
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_SECRET_KEY"] = "conversion-script-temporary-key-123456789"
os.environ["DB_NAME"] = "community_scanner_dev"

import django
django.setup()

from django.apps import apps

for model in apps.get_models():
    table = model._meta.db_table
    fields = []
    for f in model._meta.concrete_fields:
        fields.append((f.column, f.get_internal_type(), f.attname))
    print(f"Model: {model.__name__} -> Table: {table}")
    for col, itype, att in fields:
        if itype == "BooleanField":
            print(f"  BOOL: {col} ({itype})")

