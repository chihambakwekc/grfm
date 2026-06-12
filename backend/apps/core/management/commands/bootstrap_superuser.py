from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update one real GRFM system administrator profile. No demo data is created."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--phone", default="")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        if not username:
            raise CommandError("Username is required.")
        if not password:
            raise CommandError("Password is required.")

        user, created = User.objects.get_or_create(username=username)
        user.email = options["email"].strip()
        user.first_name = options["first_name"].strip()
        user.last_name = options["last_name"].strip()
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.Role.SYS_ADMIN
        profile.phone = options["phone"].strip()
        profile.active = True
        profile.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} GRFM system administrator: {username}"))
