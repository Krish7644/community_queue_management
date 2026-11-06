"""Compare the imported legacy rows without printing records or credential values."""
import json
from pathlib import Path
import MySQLdb
import MySQLdb.cursors
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
config = dotenv_values(ROOT / "backend/.env")
connection = MySQLdb.connect(host="127.0.0.1", port=3306, user=config["DB_USER"], passwd=config["DB_PASSWORD"],
    charset="utf8mb4", cursorclass=MySQLdb.cursors.DictCursor)
report = {"source": "community_scanner_legacy", "target": "community_scanner_dev", "tables": {}, "all_rows_match": True}
with connection.cursor() as cursor:
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='community_scanner_legacy' ORDER BY table_name")
    tables = [row["TABLE_NAME"] if "TABLE_NAME" in row else row["table_name"] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f"SELECT * FROM community_scanner_legacy.`{table}` ORDER BY id")
        source = list(cursor.fetchall())
        cursor.execute(f"SELECT * FROM community_scanner_dev.`{table}` ORDER BY id")
        target = list(cursor.fetchall())
        for rows in (source, target):
            for row in rows:
                row.pop("password", None)
        match = source == target
        report["tables"][table] = {"source_rows": len(source), "target_rows": len(target), "match": match}
        report["all_rows_match"] = report["all_rows_match"] and match
    cursor.execute("SELECT COUNT(*) AS total FROM community_scanner_dev.portal_user WHERE password NOT LIKE 'plaintext$%'")
    report["all_account_passwords_readable"] = cursor.fetchone()["total"] == 0
    report["legacy_password_columns_managed"] = True
    for table in ("admins", "authorities", "scanners", "volunteers"):
        cursor.execute(f"SELECT COUNT(*) AS total FROM community_scanner_dev.`{table}` WHERE password <> '!managed-by-django'")
        report["legacy_password_columns_managed"] = report["legacy_password_columns_managed"] and cursor.fetchone()["total"] == 0
connection.close()
(ROOT / "migration-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(f"Compared {len(tables)} tables; original rows and QR tokens match: {report['all_rows_match']}.")
print(f"Accounts use readable password storage: {report['all_account_passwords_readable']}.")
if not report["all_rows_match"] or not report["all_account_passwords_readable"] or not report["legacy_password_columns_managed"]:
    raise SystemExit(1)
