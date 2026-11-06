import os
import re
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_SECRET_KEY"] = "temp-key"
os.environ["DB_NAME"] = "community_scanner_dev"

import django
django.setup()

from django.apps import apps
from test_parser import parse_mysql_values

dump_path = Path(r"C:\Users\littl\Downloads\community_scanner_dev.sql")
text = dump_path.read_text(encoding="utf-8", errors="ignore")

# Map of table_name -> Model
table_to_model = {}
for model in apps.get_models():
    table_to_model[model._meta.db_table] = model

# Parse CREATE TABLE column order
table_cols = {}
table_blocks = re.findall(r"CREATE TABLE `(\w+)` \((.*?)\) ENGINE=", text, re.DOTALL)
for tname, body in table_blocks:
    cols = []
    for line in body.strip().splitlines():
        line = line.strip()
        m = re.match(r"`(\w+)`\s+([^\s,]+)", line)
        if m:
            cols.append(m.group(1))
    table_cols[tname] = cols

fixtures = []

# List of application tables to export as fixture (in FK dependency order)
app_tables = [
    'admins',
    'gates',
    'authorities',
    'scanners',
    'volunteers',
    'portal_user',
    'community_members',
    'qr_tokens',
    'hod_passes',
    'congregation_combined_passes',
    'vvip_batches',
    'vvip_passes',
    'volunteer_pass_batches',
    'volunteer_passes',
    'immediate_passes',
    'entry_logs',
    'approval_history',
    'profile_edit_requests',
    'audit_logs',
    'portal_eventsettings',
    'portal_scanreceipt'
]

for tname in app_tables:
    model = table_to_model.get(tname)
    if not model:
        continue
    
    pattern = rf"INSERT INTO `{tname}` VALUES (.*?);\n"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        continue
    
    rows = parse_mysql_values(m.group(1))
    cols = table_cols.get(tname, [])
    
    # Map column names to model field objects
    col_to_field = {}
    for f in model._meta.concrete_fields:
        col_to_field[f.column] = f
    
    for r in rows:
        row_dict = dict(zip(cols, r))
        pk_val = row_dict.get('id')
        fields_data = {}
        
        for col_name, val in row_dict.items():
            if col_name == 'id':
                continue
            f = col_to_field.get(col_name)
            if not f:
                continue
            
            field_name = f.attname
            itype = f.get_internal_type()
            
            if val is None:
                fields_data[field_name] = None
            elif itype == "BooleanField":
                fields_data[field_name] = str(val).strip() in ("1", "True", "true")
            elif itype in ("IntegerField", "PositiveIntegerField", "PositiveSmallIntegerField", "BigIntegerField", "PositiveBigIntegerField"):
                try:
                    fields_data[field_name] = int(val)
                except ValueError:
                    fields_data[field_name] = val
            elif itype == "JSONField":
                try:
                    fields_data[field_name] = json.loads(val)
                except:
                    fields_data[field_name] = val
            else:
                fields_data[field_name] = str(val)
        
        fixtures.append({
            "model": f"{model._meta.app_label}.{model._meta.model_name}",
            "pk": int(pk_val) if str(pk_val).isdigit() else pk_val,
            "fields": fields_data
        })

fixtures_path = Path(__file__).resolve().parent.parent / "backend/portal/fixtures"
fixtures_path.mkdir(parents=True, exist_ok=True)
json_file = fixtures_path / "initial_data.json"
json_file.write_text(json.dumps(fixtures, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Generated Django fixture with {len(fixtures)} records at: {json_file}")

