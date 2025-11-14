
from django.core.management.base import BaseCommand
from repeaters.models import RepeaterDevice
from repeaters.utils import hash_new_api_key
import secrets

class Command(BaseCommand):
    help = "Create a new repeater device and print its API key (store securely on the device)."

    def add_arguments(self, parser):
        parser.add_argument("device", type=str, help="Device ID, e.g., RPT001")
        parser.add_argument("--friendly", type=str, default="", help="Friendly name")
        parser.add_argument("--no-key", action="store_true", help="Do not generate an API key (open device)")

    def handle(self, *args, **opts):
        device_id = opts["device"]
        friendly = opts["friendly"]

        api_key = None
        salt = ""
        api_key_hash = ""
        if not opts["no_key"]:
            api_key = secrets.token_urlsafe(24)
            salt, api_key_hash = hash_new_api_key(api_key)

        obj, created = RepeaterDevice.objects.update_or_create(
            device=device_id,
            defaults={
                "friendly_name": friendly,
                "salt": salt,
                "api_key_hash": api_key_hash,
                "enabled": True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created device {device_id}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated device {device_id}"))

        if api_key:
            self.stdout.write(self.style.MIGRATE_HEADING("API KEY (save this to device):"))
            self.stdout.write(self.style.SUCCESS(api_key))
        else:
            self.stdout.write("No API key set; device is OPEN (not recommended for production).")
