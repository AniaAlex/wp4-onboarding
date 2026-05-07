"""
Views for the operator-facing UI and the public /lists/* endpoints.

The /lists/* endpoints match the contract described in
../onboarding/pb_public/openapi.yaml — same URL pattern, same response shape.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .etsi import build_etsi_lote
from .models import (
    ENTITY_TYPE_FOR_LIST,
    LIST_BASENAME,
    SERVICE_TYPE_FOR_LIST,
    SVCSTATUS_GRANTED,
    SVCSTATUS_NOTIFIED,
    Entity,
    ListType,
    LotlPointer,
    Scheme,
)

_STATIC_DIR = Path(__file__).resolve().parent / "static" / "trustlists"


# Reverse map: filename basename → ListType value
BASENAME_TO_LIST = {v: k for k, v in LIST_BASENAME.items()}


# ─────────────── liveness / readiness ───────────────


@require_GET
def healthz(request: HttpRequest) -> HttpResponse:
    """Liveness probe — used by Docker HEALTHCHECK and k8s readinessProbe.

    Returns 200 ok if the process is up. Does not check DB connectivity
    (a hung DB shouldn't make us thrash-restart). For deeper checks, add
    a separate /readyz/ that runs `connection.ensure_connection()`.
    """
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")


# ─────────────── operator UI ───────────────


def root(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")
    errors: dict[str, str] = {}
    form_data = {"email": ""}
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        form_data["email"] = email
        user = authenticate(request, username=email, password=password)
        if user is None:
            errors["credentials"] = "Email or password is incorrect."
        else:
            login(request, user)
            return redirect("dashboard")
    return render(request, "trustlists/login.html", {"errors": errors, "form_data": form_data})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    schemes = Scheme.objects.filter(owner=request.user).order_by("list_type")
    rows = []
    for s in schemes:
        if s.is_lotl:
            cnt = s.lotl_pointers.count()
        else:
            cnt = s.entities.count()
        rows.append(
            {
                "id": s.id,
                "list_type": s.list_type,
                "list_type_label": s.get_list_type_display(),
                "territory": s.territory,
                "sequence_number": s.sequence_number,
                "entity_count": cnt,
                "is_lotl": s.is_lotl,
                "public_url": s.public_url,
            }
        )
    return render(request, "trustlists/dashboard.html", {"schemes": rows})


@login_required
def scheme_detail(request: HttpRequest, scheme_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    ctx: dict = {
        "scheme": scheme,
        "is_lotl": scheme.is_lotl,
    }
    if scheme.is_lotl:
        ctx["pointers"] = list(scheme.lotl_pointers.all())
    else:
        ctx["entities"] = list(scheme.entities.all())
    return render(request, "trustlists/scheme_detail.html", ctx)


# ─────────────── public trust-list endpoints ───────────────
#
# Matches the contract from the Pocketbase version:
#   GET /lists/                                → HTML directory
#   GET /lists/index.json                      → manifest
#   GET /lists/<basename>-<territory>.json     → unsigned LoTE / LoTL


@require_GET
def lists_index_html(request: HttpRequest) -> HttpResponse:
    schemes = Scheme.objects.order_by("list_type")
    return render(request, "trustlists/lists_index.html", {"schemes": schemes})


@require_GET
def lists_manifest(request: HttpRequest) -> JsonResponse:
    items = [
        {
            "list_type": s.list_type,
            "territory": s.territory,
            "url": s.public_url,
        }
        for s in Scheme.objects.order_by("list_type")
    ]
    resp = JsonResponse({"lists": items}, json_dumps_params={"indent": 2})
    resp["Cache-Control"] = "no-store"
    return resp


@require_GET
def list_unsigned(request: HttpRequest, filename: str) -> HttpResponse:
    # filename pattern: <basename>-<territory>.json (case-insensitive territory)
    if not filename.endswith(".json"):
        return JsonResponse({"error": "not_found", "filename": filename}, status=404)
    stem = filename[:-len(".json")]
    if "-" not in stem:
        return JsonResponse({"error": "not_found", "filename": filename}, status=404)
    basename, _, territory = stem.rpartition("-")
    basename = basename.lower()
    territory = territory.upper()
    list_type = BASENAME_TO_LIST.get(basename)
    if list_type is None:
        return JsonResponse({"error": "unknown_list_type", "basename": basename}, status=404)

    try:
        scheme = Scheme.objects.get(list_type=list_type, territory=territory)
    except Scheme.DoesNotExist:
        return JsonResponse(
            {"error": "scheme_not_found", "listType": list_type, "territory": territory},
            status=404,
        )

    payload = build_etsi_lote(scheme)
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    resp = HttpResponse(body, content_type="application/json; charset=utf-8")
    resp["Cache-Control"] = "no-store"
    return resp


# ─────────────── entity create / edit / delete ───────────────


PLACEHOLDERS = {
    ListType.PID: {
        "entity_id":    "https://eid.example.se/pid",
        "info_uri":     "https://www.example.se/eid",
        "service_name": "Example PID Issuance Service",
    },
    ListType.WALLET: {
        "entity_id":    "https://wallet.example.se",
        "info_uri":     "https://www.example.se/wallet",
        "service_name": "Example Wallet Solution",
    },
    ListType.PUBEAA: {
        "entity_id":    "https://eaa.example.se",
        "info_uri":     "https://www.example.se/eaa",
        "service_name": "Example PubEAA Issuance Service",
    },
    ListType.WRPAC: {
        "entity_id":    "https://wrpac.example.se",
        "info_uri":     "https://www.example.se/wrpac",
        "service_name": "Example WRPAC Service",
    },
    ListType.WRPRC: {
        "entity_id":    "https://wrprc.example.se",
        "info_uri":     "https://www.example.se/wrprc",
        "service_name": "Example WRPRC Service",
    },
    ListType.REGISTRAR: {
        "entity_id":    "https://eregister.example.se",
        "info_uri":     "https://www.example.se/registrar",
        "service_name": "Example Registrar Service",
    },
}

SERVICE_TYPE_LABEL = {
    ListType.PID:       "PIDProvider",
    ListType.WALLET:    "WalletSolution/Issuance",
    ListType.PUBEAA:    "PubEAAProvider",
    ListType.WRPAC:     "WRPACProvider",
    ListType.WRPRC:     "WRPRCProvider",
    ListType.REGISTRAR: "Registrar",
}


def _multilang_pairs(post, lang_key: str, val_key: str) -> list[dict]:
    langs = post.getlist(lang_key + "[]")
    values = post.getlist(val_key + "[]")
    out = []
    for lang, value in zip(langs, values):
        if lang and value:
            out.append({"language": lang, "value": value})
    return out


def _string_list(post, key: str) -> list[str]:
    return [v for v in post.getlist(key + "[]") if v]


def _try_json(s: str):
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None


def _entity_form_context(scheme: Scheme, *, entity: Entity | None) -> dict:
    lt = scheme.list_type
    show_status = lt == ListType.PUBEAA

    if entity is None:
        form_data = {
            "entity_id": "", "status": SVCSTATUS_NOTIFIED, "names": [],
            "addr_street": "", "addr_city": "", "addr_postal": "",
            "addr_country": scheme.territory,
            "electronic": [], "information_uri": [],
            "service_names": [],
            "jwk_text": "", "did_uri": "", "cert_pem": "",
        }
    else:
        addr = entity.address or {}
        postal = addr.get("postal", {}) if isinstance(addr, dict) else {}
        electronic = addr.get("electronic", []) if isinstance(addr, dict) else []
        services = entity.services or []
        svc0 = services[0] if services else {}
        form_data = {
            "entity_id": entity.entity_id,
            "status": entity.status or SVCSTATUS_NOTIFIED,
            "names": entity.names or [],
            "addr_street": postal.get("streetAddress", ""),
            "addr_city": postal.get("locality", ""),
            "addr_postal": postal.get("postalCode", ""),
            "addr_country": postal.get("countryName", scheme.territory),
            "electronic": electronic,
            "information_uri": entity.information_uri or [],
            "service_names": svc0.get("serviceNames", []),
            "jwk_text": json.dumps(entity.jwk) if entity.jwk else "",
            "did_uri": entity.did_uri or "",
            "cert_pem": entity.cert_pem or "",
        }

    return {
        "scheme": scheme,
        "entity": entity,
        "show_status": show_status,
        "service_type_label": SERVICE_TYPE_LABEL.get(lt, ""),
        "placeholders": PLACEHOLDERS.get(lt, PLACEHOLDERS[ListType.PID]),
        "form_data": form_data,
    }


def _save_entity_from_post(scheme: Scheme, post, *, entity: Entity | None) -> Entity:
    """Apply form POST to a new or existing entity and save."""
    lt = scheme.list_type
    is_pubeaa = lt == ListType.PUBEAA

    names = _multilang_pairs(post, "names_lang", "names_value")
    info_uris = _multilang_pairs(post, "info_lang", "info_value")
    service_names = _multilang_pairs(post, "svcname_lang", "svcname_value")
    electronic = _string_list(post, "electronic")

    address: dict = {
        "postal": {
            "streetAddress": post.get("addr_street", ""),
            "locality":      post.get("addr_city", ""),
            "postalCode":    post.get("addr_postal", ""),
            "countryName":   post.get("addr_country", ""),
        }
    }
    if electronic:
        address["electronic"] = electronic

    entity_status = post.get("status", "") if is_pubeaa else ""
    service_status = (entity_status or SVCSTATUS_NOTIFIED) if is_pubeaa else SVCSTATUS_GRANTED

    services = [{
        "serviceNames": service_names,
        "serviceType":  SERVICE_TYPE_FOR_LIST.get(lt, ""),
        "status":       service_status,
    }]

    if entity is None:
        entity = Entity(scheme=scheme)

    entity.entity_id = post.get("entity_id", "")
    entity.entity_type = ENTITY_TYPE_FOR_LIST.get(lt, "")
    entity.status = entity_status
    entity.names = names
    entity.address = address
    entity.information_uri = info_uris
    entity.services = services
    entity.cert_pem = post.get("cert_pem", "")
    entity.jwk = _try_json(post.get("jwk_text", "")) or {}
    entity.did_uri = post.get("did_uri", "")
    entity.save()
    return entity


@login_required
@require_http_methods(["GET", "POST"])
def entity_create(request: HttpRequest, scheme_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    if scheme.is_lotl:
        return redirect("pointer_create", scheme_id=scheme.id)
    if request.method == "POST":
        _save_entity_from_post(scheme, request.POST, entity=None)
        return redirect("scheme_detail", scheme_id=scheme.id)
    ctx = _entity_form_context(scheme, entity=None)
    return render(request, "trustlists/entity_form.html", ctx)


@login_required
@require_http_methods(["GET", "POST"])
def entity_edit(request: HttpRequest, scheme_id: int, entity_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    entity = get_object_or_404(Entity, pk=entity_id, scheme=scheme)
    if request.method == "POST":
        _save_entity_from_post(scheme, request.POST, entity=entity)
        return redirect("scheme_detail", scheme_id=scheme.id)
    ctx = _entity_form_context(scheme, entity=entity)
    return render(request, "trustlists/entity_form.html", ctx)


@login_required
@require_http_methods(["POST"])
def entity_delete(request: HttpRequest, scheme_id: int, entity_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    entity = get_object_or_404(Entity, pk=entity_id, scheme=scheme)
    entity.delete()
    return redirect("scheme_detail", scheme_id=scheme.id)


# ─────────────── LoTL pointer create / edit / delete ───────────────


SCHEME_TYPE_OPTIONS_FOR_POINTERS = [
    {
        "value": "http://uri.etsi.org/19602/LoTEType/EUPIDProvidersList",
        "label": "EU PID Providers",
    },
    {
        "value": "http://uri.etsi.org/19602/LoTEType/EUWalletProvidersList",
        "label": "EU Wallet Providers",
    },
    {
        "value": "http://uri.etsi.org/19602/LoTEType/EUPubEAAProvidersList",
        "label": "EU PubEAA Providers",
    },
    {
        "value": "http://uri.etsi.org/19602/LoTEType/EUWRPACProvidersList",
        "label": "EU WRPAC Providers",
    },
    {
        "value": "http://uri.etsi.org/19602/LoTEType/EUWRPRCProvidersList",
        "label": "EU WRPRC Providers",
    },
    {
        "value": "http://uri.etsi.org/19602/LoTEType/EURegistrarsAndRegistersList",
        "label": "EU Registrars and Registers",
    },
]


def _pointer_form_context(scheme: Scheme, *, pointer: LotlPointer | None) -> dict:
    if pointer is None:
        form_data = {
            "location": "", "scheme_territory": "", "scheme_type": "",
            "mime_type": "application/json", "scheme_operator_names": [],
        }
    else:
        form_data = {
            "location": pointer.location,
            "scheme_territory": pointer.scheme_territory,
            "scheme_type": pointer.scheme_type,
            "mime_type": pointer.mime_type,
            "scheme_operator_names": pointer.scheme_operator_names or [],
        }
    return {
        "scheme": scheme,
        "pointer": pointer,
        "scheme_type_options": SCHEME_TYPE_OPTIONS_FOR_POINTERS,
        "form_data": form_data,
    }


def _save_pointer_from_post(scheme: Scheme, post, *, pointer: LotlPointer | None) -> LotlPointer:
    op_names = _multilang_pairs(post, "opnames_lang", "opnames_value")
    if pointer is None:
        pointer = LotlPointer(scheme=scheme)
    pointer.location = post.get("location", "")
    pointer.scheme_territory = post.get("scheme_territory", "").upper()
    pointer.scheme_type = post.get("scheme_type", "")
    pointer.scheme_operator_names = op_names
    pointer.mime_type = post.get("mime_type", "application/json")
    pointer.save()
    return pointer


@login_required
@require_http_methods(["GET", "POST"])
def pointer_create(request: HttpRequest, scheme_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    if not scheme.is_lotl:
        return redirect("entity_create", scheme_id=scheme.id)
    if request.method == "POST":
        _save_pointer_from_post(scheme, request.POST, pointer=None)
        return redirect("scheme_detail", scheme_id=scheme.id)
    ctx = _pointer_form_context(scheme, pointer=None)
    return render(request, "trustlists/pointer_form.html", ctx)


@login_required
@require_http_methods(["GET", "POST"])
def pointer_edit(request: HttpRequest, scheme_id: int, pointer_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    pointer = get_object_or_404(LotlPointer, pk=pointer_id, scheme=scheme)
    if request.method == "POST":
        _save_pointer_from_post(scheme, request.POST, pointer=pointer)
        return redirect("scheme_detail", scheme_id=scheme.id)
    ctx = _pointer_form_context(scheme, pointer=pointer)
    return render(request, "trustlists/pointer_form.html", ctx)


@login_required
@require_http_methods(["POST"])
def pointer_delete(request: HttpRequest, scheme_id: int, pointer_id: int) -> HttpResponse:
    scheme = get_object_or_404(Scheme, pk=scheme_id, owner=request.user)
    pointer = get_object_or_404(LotlPointer, pk=pointer_id, scheme=scheme)
    pointer.delete()
    return redirect("scheme_detail", scheme_id=scheme.id)


# ─────────────── OpenAPI / Swagger UI ───────────────


@require_GET
def openapi_yaml(request: HttpRequest) -> HttpResponse:
    """Serve the OpenAPI 3 spec describing the public /lists/* contract."""
    spec_path = _STATIC_DIR / "openapi.yaml"
    return HttpResponse(
        spec_path.read_text(encoding="utf-8"),
        content_type="application/yaml; charset=utf-8",
    )


@require_GET
def swagger_ui(request: HttpRequest) -> HttpResponse:
    """Browser-friendly Swagger UI rendering the spec."""
    page_path = _STATIC_DIR / "swagger" / "index.html"
    return HttpResponse(
        page_path.read_text(encoding="utf-8"),
        content_type="text/html; charset=utf-8",
    )
