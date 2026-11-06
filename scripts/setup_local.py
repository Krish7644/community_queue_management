"""Create isolated local databases. Never connects to production or modifies old schemas."""
import os
import secrets
import subprocess
from pathlib import Path

import MySQLdb
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / "backend/.env"
config = dict(dotenv_values(ENV)) if ENV.exists() else {}
password = config.get("DB_PASSWORD") or secrets.token_urlsafe(32)
admin_password = os.environ.get("MYSQL_ADMIN_PASSWORD")
if not admin_password:
    from getpass import getpass
    admin_password = getpass("Local MySQL root password: ")
connection = MySQLdb.connect(host="127.0.0.1", port=3306, user="root", passwd=admin_password, charset="utf8mb4", autocommit=True)
with connection.cursor() as cursor:
    for name in ("community_scanner_legacy", "community_scanner_dev"):
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute("CREATE USER IF NOT EXISTS 'community_scanner_app'@'127.0.0.1' IDENTIFIED BY %s", [password])
    for name in ("community_scanner_dev", "test_community_scanner_dev"):
        cursor.execute(f"GRANT ALL PRIVILEGES ON `{name}`.* TO 'community_scanner_app'@'127.0.0.1'")
    cursor.execute("GRANT SELECT ON community_scanner_legacy.* TO 'community_scanner_app'@'127.0.0.1'")
    cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='community_scanner_legacy'")
    count = cursor.fetchone()[0]
connection.close()
if count == 0:
    dump = Path(os.environ.get("LEGACY_SQL_DUMP", str(Path.home() / "Downloads/rajpu485_SKJ_pass.sql")))
    environment = os.environ.copy()
    environment["MYSQL_PWD"] = admin_password
    client = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
    with dump.open("rb") as source:
        subprocess.run([client, "--no-defaults", "--protocol=TCP", "--host=127.0.0.1", "--port=3306", "--user=root", "--default-character-set=utf8mb4", "community_scanner_legacy"], stdin=source, env=environment, check=True)
    print("SQL dump restored into community_scanner_legacy.")
elif count != 18:
    raise SystemExit("Legacy schema has an unexpected table count; refusing to import over existing data.")
if not ENV.exists():
    legacy_public = Path.home() / "Downloads/projects/janmashtami_qline_scanner/public"
    ENV.write_text("\n".join([
        "DJANGO_DEBUG=1", f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}", "DB_NAME=community_scanner_dev",
        "DB_USER=community_scanner_app", f"DB_PASSWORD={password}", f"LEGACY_PUBLIC={legacy_public.as_posix()}", "",
    ]), encoding="utf-8")
print("Isolated databases and application credentials are ready. Root credentials were not saved.")
