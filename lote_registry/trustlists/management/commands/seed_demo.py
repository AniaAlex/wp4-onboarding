"""
Seed a demo operator + 7 schemes (one per list type), idempotent.

Run: `python manage.py seed_demo`  (or via Makefile: `make seed`)
"""
import os

from django.core.management.base import BaseCommand

from lote_registry.trustlists.models import (
    LIST_BASENAME,
    SCHEME_TYPE_URI,
    ListType,
    Operator,
    Scheme,
)

DEMO_EMAIL = os.environ.get("DEMO_OPERATOR_EMAIL", "operator@wp4trust.local")
DEMO_PASSWORD = os.environ.get("DEMO_OPERATOR_PASSWORD", "demo-pass-12345")


class Command(BaseCommand):
    help = "Seed a demo operator and one scheme per list type. Idempotent."

    def handle(self, *args, **opts):
        op, op_created = Operator.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={
                "display_name": "Demo Operator",
                "territory": "EU",
                "role": Operator.Role.PUBLISHER,
                "is_active": True,
            },
        )
        if op_created:
            op.set_password(DEMO_PASSWORD)
            op.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"Created operator {DEMO_EMAIL}"))
        else:
            self.stdout.write(f"Operator {DEMO_EMAIL} already exists")

        for list_type, label in ListType.choices:
            scheme, created = Scheme.objects.get_or_create(
                list_type=list_type,
                territory="EU",
                defaults={
                    "scheme_type": SCHEME_TYPE_URI[list_type],
                    "operator_names": [{"language": "en", "value": "WP4Trust Demo Registry"}],
                    "scheme_name": [{"language": "en", "value": label.replace("EU ", "EU ")}],
                    "sequence_number": 1,
                    "owner": op,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Created scheme: {label} → /lists/{LIST_BASENAME[list_type]}-EU.json"
                ))
            else:
                self.stdout.write(f"Scheme exists: {label}")

        self.stdout.write(self.style.SUCCESS(
            f"\nLogin at /login/ as {DEMO_EMAIL} / {DEMO_PASSWORD}"
        ))
