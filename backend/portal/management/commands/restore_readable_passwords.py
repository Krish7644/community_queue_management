"""Restore verified original credentials from the user's isolated SQL snapshot."""
import MySQLdb
import MySQLdb.cursors
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from portal.models import User
from portal.passwords import readable_password


class Command(BaseCommand):
    help = "Restore matching backup passwords to readable storage; never reset changed passwords."
    target_database = "community_scanner_dev"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Save verified originals. Default: report counts only.")

    def handle(self, *args, **options):
        if connection.settings_dict["NAME"] != self.target_database:
            raise CommandError("This command only writes to the local community_scanner_dev database.")
        source = MySQLdb.connect(host="127.0.0.1", port=3306, user=settings.DATABASES["default"]["USER"],
            passwd=settings.DATABASES["default"]["PASSWORD"], db=settings.LEGACY_DATABASE,
            charset="utf8mb4", cursorclass=MySQLdb.cursors.DictCursor)
        originals = {}
        try:
            with source.cursor() as reader:
                for table in ("admins", "authorities", "scanners", "volunteers"):
                    reader.execute(f"SELECT id,password FROM `{table}`")
                    originals[table] = {row["id"]: row["password"] for row in reader.fetchall()}
        finally:
            source.close()
        restored = unavailable = already_readable = 0
        with transaction.atomic():
            accounts = User.objects.order_by("pk")
            if options["apply"]:
                accounts = accounts.select_for_update()
            for user in accounts:
                if readable_password(user) is not None:
                    already_readable += 1
                    continue
                original = originals.get(user.source_table, {}).get(user.legacy_id)
                if not isinstance(original, str) or not check_password(original, user.password):
                    unavailable += 1
                    continue
                if options["apply"]:
                    user.set_password(original)
                    user.save(update_fields=["password"])
                restored += 1
        verb = "Restored" if options["apply"] else "Recoverable"
        self.stdout.write(f"{verb}: {restored}; already readable: {already_readable}; original unavailable/changed: {unavailable}.")
        if unavailable:
            self.stdout.write("Unmatched accounts were preserved. They need their current password at login or an administrator reset.")
        self.stdout.write("No password values were printed. Restart the backend and sign in again after applying.")
