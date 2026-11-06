"""Copy the local SQL snapshot, preserving primary keys and QR tokens."""
import os
import MySQLdb
import MySQLdb.cursors
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from portal.models import User


class Command(BaseCommand):
    help = "Import the isolated local legacy database once, retaining readable account passwords."

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != "community_scanner_dev":
            raise CommandError("This importer only writes to community_scanner_dev.")
        if User.objects.exists():
            raise CommandError("Accounts already exist. Import is one-time and never overwrites application data.")
        source = MySQLdb.connect(host="127.0.0.1", port=3306, user=settings.DATABASES["default"]["USER"],
            passwd=settings.DATABASES["default"]["PASSWORD"], db=settings.LEGACY_DATABASE, charset="utf8mb4", cursorclass=MySQLdb.cursors.DictCursor)
        roles = {"admins": "ADMIN", "authorities": "AUTHORITY", "volunteers": "VOLUNTEER", "scanners": "SCANNER"}
        excluded = {"portal_user", "portal_scanreceipt", "portal_eventsettings"}
        models = [model for model in apps.get_app_config("portal").get_models() if model._meta.db_table not in excluded]
        for model in models:
            if model.objects.exists():
                raise CommandError(f"{model._meta.db_table} already contains rows; refusing to overwrite.")
        accounts = []
        counts = {}
        connection.disable_constraint_checking()
        try:
            with transaction.atomic(), source.cursor() as reader, connection.cursor() as writer:
                for model in models:
                    table = model._meta.db_table
                    reader.execute(f"SELECT * FROM `{table}`")
                    rows = reader.fetchall()
                    columns = [field.column for field in model._meta.local_fields]
                    if rows and set(columns) - set(rows[0]):
                        raise CommandError(f"Schema mismatch for {table}.")
                    if table in roles:
                        accounts.extend((roles[table], table, row.copy()) for row in rows)
                        for row in rows:
                            row["password"] = "!managed-by-django"
                    if rows:
                        placeholders = ",".join(["%s"] * len(columns))
                        quoted = ",".join(f"`{column}`" for column in columns)
                        writer.executemany(f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders})", [[row[column] for column in columns] for row in rows])
                    counts[table] = len(rows)
                for role, table, row in accounts:
                    user = User(username=f"{role.lower()}.{row['id']}", login_id=row["username"], display_name=row["name"],
                        source_table=table, legacy_id=row["id"], role=role, is_active=row["status"] == "ACTIVE", is_staff=role == "ADMIN")
                    user.set_password(row["password"])
                    user.save()
                connection.check_constraints(table_names=list(counts))
        finally:
            connection.enable_constraint_checking()
            source.close()
        for table, count in counts.items():
            self.stdout.write(f"{table}: {count} rows preserved")
        self.stdout.write(self.style.SUCCESS(f"Migrated {len(accounts)} accounts with readable password storage. QR tokens and entry history preserved."))
