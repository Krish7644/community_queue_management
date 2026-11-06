from django.core.management import call_command
from django.core.management.base import BaseCommand
from portal.models import User

class Command(BaseCommand):
    help = "Loads converted PostgreSQL data on initial deployment if database is empty."

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write(self.style.SUCCESS("Database already contains data. Skipping initial fixture import."))
            return

        self.stdout.write("Database is empty. Populating 2,068 converted records from initial_data.json...")
        call_command("loaddata", "initial_data.json")
        self.stdout.write(self.style.SUCCESS(f"Successfully loaded initial database! Total users: {User.objects.count()}"))

