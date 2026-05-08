"""
Data model for the WP4Trust trust-list onboarding app.

Mirrors the Pocketbase collections so the OpenAPI contract and the public
/lists/* endpoints behave identically across both implementations.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


# ─────────────── auth: operators (custom user model) ───────────────


class OperatorManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("territory", "EU")
        extra.setdefault("display_name", email.split("@")[0])
        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create(email, password, **extra)


class Operator(AbstractUser):
    """End-user account. The username field is dropped — we authenticate by email."""

    username = None
    email = models.EmailField("email address", unique=True)
    display_name = models.CharField(max_length=100)
    territory = models.CharField(
        max_length=3,
        help_text="ISO 3166-1 alpha-2 of the operator's MS, or 'EU' for cross-border",
    )

    class Role(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        EDITOR = "editor", "Editor"
        PUBLISHER = "publisher", "Publisher"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.EDITOR)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name", "territory"]

    objects = OperatorManager()

    def __str__(self) -> str:  # admin display
        return f"{self.display_name} <{self.email}>"


# ─────────────── trust-list domain ───────────────


class ListType(models.TextChoices):
    PID = "pid", "EU PID Providers"
    WALLET = "wallet", "EU Wallet Providers"
    PUBEAA = "pubeaa", "EU PubEAA Providers"
    WRPAC = "wrpac", "EU WRPAC Providers"
    WRPRC = "wrprc", "EU WRPRC Providers"
    REGISTRAR = "registrar", "EU Registrars and Registers"
    LOTL = "lotl", "EU List of Trusted Lists"


SCHEME_TYPE_URI = {
    ListType.PID: "http://uri.etsi.org/19602/LoTEType/EUPIDProvidersList",
    ListType.WALLET: "http://uri.etsi.org/19602/LoTEType/EUWalletProvidersList",
    ListType.PUBEAA: "http://uri.etsi.org/19602/LoTEType/EUPubEAAProvidersList",
    ListType.WRPAC: "http://uri.etsi.org/19602/LoTEType/EUWRPACProvidersList",
    ListType.WRPRC: "http://uri.etsi.org/19602/LoTEType/EUWRPRCProvidersList",
    ListType.REGISTRAR: "http://uri.etsi.org/19602/LoTEType/EURegistrarsAndRegistersList",
    ListType.LOTL: "http://uri.etsi.org/19602/LoTLType/EUListOfTrustedLists",
}

LIST_BASENAME = {
    ListType.PID: "pid_providers",
    ListType.WALLET: "wallet_providers",
    ListType.PUBEAA: "pubeaa_providers",
    ListType.WRPAC: "wrpac_providers",
    ListType.WRPRC: "wrprc_providers",
    ListType.REGISTRAR: "registrars_registers",
    ListType.LOTL: "list_of_trusted_lists",
}

ENTITY_TYPE_FOR_LIST = {
    ListType.PID: "pid-provider",
    ListType.WALLET: "wallet-provider",
    ListType.PUBEAA: "pubeaa-provider",
    ListType.WRPAC: "wrpac-provider",
    ListType.WRPRC: "wrprc-provider",
    ListType.REGISTRAR: "registrar",
}

SERVICE_TYPE_FOR_LIST = {
    ListType.PID: "http://uri.etsi.org/19602/SvcType/PIDProvider",
    ListType.WALLET: "http://uri.etsi.org/19602/SvcType/WalletSolution/Issuance",
    ListType.PUBEAA: "http://uri.etsi.org/19602/SvcType/PubEAAProvider",
    ListType.WRPAC: "http://uri.etsi.org/19602/SvcType/WRPACProvider",
    ListType.WRPRC: "http://uri.etsi.org/19602/SvcType/WRPRCProvider",
    ListType.REGISTRAR: "http://uri.etsi.org/19602/SvcType/Registrar",
}

SVCSTATUS_GRANTED = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/granted"
SVCSTATUS_NOTIFIED = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/notified"
SVCSTATUS_WITHDRAWN = "http://uri.etsi.org/TrstSvc/TrustedList/Svcstatus/withdrawn"


class Scheme(models.Model):
    """One row per published list (LoTE or LoTL)."""

    list_type = models.CharField(max_length=16, choices=ListType.choices)
    operator_names = models.JSONField(
        default=list,
        help_text='Array of {"language": "en", "value": "..."}',
    )
    scheme_name = models.JSONField(
        default=list,
        blank=True,
        help_text='Array of {"language": "en", "value": "..."}',
    )
    scheme_type = models.URLField(max_length=300)
    territory = models.CharField(max_length=3)
    sequence_number = models.PositiveIntegerField(default=1)
    owner = models.ForeignKey(
        "Operator",
        on_delete=models.PROTECT,
        related_name="schemes",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["list_type", "territory"],
                name="unique_list_type_territory",
            ),
        ]
        ordering = ["list_type", "territory"]

    def __str__(self) -> str:
        return f"{self.get_list_type_display()} ({self.territory})"

    @property
    def is_lotl(self) -> bool:
        return self.list_type == ListType.LOTL

    @property
    def basename(self) -> str:
        return LIST_BASENAME.get(self.list_type, self.list_type)

    @property
    def public_url(self) -> str:
        prefix = getattr(settings, "FORCE_SCRIPT_NAME", "") or ""
        return f"{prefix}/lists/{self.basename}-{self.territory}.json"


class Entity(models.Model):
    """A single trusted entity entry on a non-LoTL scheme."""

    scheme = models.ForeignKey(
        Scheme,
        on_delete=models.CASCADE,
        related_name="entities",
    )
    names = models.JSONField(default=list, help_text='Array of {"language", "value"}')
    entity_id = models.URLField(max_length=300)
    entity_type = models.CharField(max_length=32, blank=True)
    status = models.CharField(
        max_length=128,
        blank=True,
        help_text="PubEAA only — used as ServiceStatus on output.",
    )
    address = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"postal": {...}, "electronic": [...]}',
    )
    information_uri = models.JSONField(default=list, blank=True)
    services = models.JSONField(
        default=list,
        help_text="Array of service objects with serviceNames, serviceType, status",
    )

    cert_pem = models.TextField(blank=True, help_text="PEM-encoded X.509 (chain allowed)")
    jwk = models.JSONField(default=dict, blank=True, help_text="JOSE JWK object")
    did_uri = models.URLField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "entity_id"],
                name="unique_scheme_entity_id",
            ),
        ]
        ordering = ["scheme", "entity_id"]
        verbose_name_plural = "Entities"

    def __str__(self) -> str:
        primary = (self.names[0]["value"] if self.names else self.entity_id) or "(unnamed)"
        return f"{primary} ({self.scheme})"


class LotlPointer(models.Model):
    """A pointer in a LoTL to another LoTE (per ETSI 119 602 §5.4)."""

    scheme = models.ForeignKey(
        Scheme,
        on_delete=models.CASCADE,
        related_name="lotl_pointers",
        limit_choices_to={"list_type": ListType.LOTL},
    )
    location = models.URLField(max_length=300)
    scheme_territory = models.CharField(max_length=3)
    scheme_type = models.URLField(max_length=300)
    scheme_operator_names = models.JSONField(default=list, blank=True)
    mime_type = models.CharField(
        max_length=32,
        choices=[
            ("application/json", "application/json"),
            ("application/xml", "application/xml"),
        ],
        default="application/json",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheme_territory", "scheme_type"]

    def __str__(self) -> str:
        return f"{self.scheme_territory} → {self.location}"


class PublishRun(models.Model):
    """Audit row recording each publish trigger."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    scheme = models.ForeignKey(
        Scheme,
        on_delete=models.PROTECT,
        related_name="publish_runs",
    )
    triggered_by = models.ForeignKey(
        "Operator",
        on_delete=models.PROTECT,
        related_name="publish_runs",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    request_payload = models.JSONField(default=dict, blank=True)
    response = models.JSONField(default=dict, blank=True)
    fingerprint = models.CharField(max_length=128, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.scheme} @ {self.created_at:%Y-%m-%d %H:%M} [{self.status}]"
