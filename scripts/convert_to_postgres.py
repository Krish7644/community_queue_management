import os
import re
import sys
import json
from pathlib import Path

# Setup Django environment to understand models and field types
BASE_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_SECRET_KEY"] = "conversion-script-temp-key"
os.environ["DB_NAME"] = "community_scanner_dev"

import django
django.setup()

from django.apps import apps
from test_parser import parse_mysql_values

dump_path = Path(r"C:\Users\littl\Downloads\community_scanner_dev.sql")
text = dump_path.read_text(encoding="utf-8", errors="ignore")

# Map of table_name -> dict(column_name -> (field_type, is_boolean))
table_bool_cols = {}
for model in apps.get_models():
    tbl = model._meta.db_table
    bools = set()
    for f in model._meta.concrete_fields:
        if f.get_internal_type() == "BooleanField":
            bools.add(f.column)
    table_bool_cols[tbl] = bools

# Also handle auth/django tables if any
table_bool_cols["portal_user"] = {"is_superuser", "is_staff", "is_active"}

# Parse CREATE TABLE to get column order for each table
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

# Tables to migrate (skip django internal session/migration/content_type since migrate handles them, 
# but we can optionally include them or let user choose)
# For a full clone, we will include all data tables.
tables_order = [
    'django_content_type',
    'auth_permission',
    'auth_group',
    'auth_group_permissions',
    'admins',
    'gates',
    'authorities',
    'scanners',
    'volunteers',
    'portal_user',
    'portal_user_groups',
    'portal_user_user_permissions',
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
    'portal_scanreceipt',
    'django_session'
]

sql_out = []
sql_out.append("-- PostgreSQL Data Import for Community Scanner (Converted from MySQL)")
sql_out.append("-- Generated automatically for Render PostgreSQL deployment\n")
sql_out.append("BEGIN;")
sql_out.append("SET session_replication_role = 'replica'; -- Disable FK triggers during import\n")

total_rows_converted = 0
converted_stats = {}

for tname in tables_order:
    pattern = rf"INSERT INTO `{tname}` VALUES (.*?);\n"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        continue
    
    rows = parse_mysql_values(m.group(1))
    if not rows:
        continue
    
    cols = table_cols.get(tname, [])
    bool_cols = table_bool_cols.get(tname, set())
    
    col_str = ", ".join(f'"{c}"' for c in cols)
    sql_out.append(f"-- Table: {tname} ({len(rows)} rows)")
    
    # We can batch inserts into chunks of 100 for safety and speed
    chunk_size = 100
    for chunk_start in range(0, len(rows), chunk_size):
        chunk = rows[chunk_start:chunk_start + chunk_size]
        val_rows = []
        for r in chunk:
            row_vals = []
            for col_idx, val in enumerate(r):
                col_name = cols[col_idx] if col_idx < len(cols) else ""
                is_bool = col_name in bool_cols
                
                if val is None:
                    row_vals.append("NULL")
                elif is_bool:
                    if str(val).strip() in ("1", "True", "true"):
                        row_vals.append("TRUE")
                    else:
                        row_vals.append("FALSE")
                else:
                    # Postgres string escaping: replace ' with ''
                    val_str = str(val).replace("'", "''")
                    row_vals.append(f"'{val_str}'")
            val_rows.append(f"({', '.join(row_vals)})")
        
        insert_stmt = f'INSERT INTO "{tname}" ({col_str}) VALUES\n' + ",\n".join(val_rows) + ";"
        sql_out.append(insert_stmt)
    
    sql_out.append("")
    total_rows_converted += len(rows)
    converted_stats[tname] = len(rows)

sql_out.append("\n-- Update all primary key sequences so future inserts get correct IDs")
for tname in tables_order:
    cols = table_cols.get(tname, [])
    if 'id' in cols:
        seq_update = (
            f"SELECT setval(pg_get_serial_sequence('\"{tname}\"', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM \"{tname}\"), 1));"
        )
        sql_out.append(seq_update)

sql_out.append("\nSET session_replication_role = 'origin'; -- Re-enable FK triggers")
sql_out.append("COMMIT;")

output_file = Path(__file__).resolve().parent.parent / "render_postgres_data.sql"
output_file.write_text("\n".join(sql_out), encoding="utf-8")

print(f"Successfully converted {total_rows_converted} rows across {len(converted_stats)} tables!")
for tbl, cnt in converted_stats.items():
    print(f"  {tbl}: {cnt} rows")
print(f"\nWritten to: {output_file} ({output_file.stat().st_size} bytes)")

