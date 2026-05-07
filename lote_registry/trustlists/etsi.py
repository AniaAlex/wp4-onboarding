"""
Build the canonical ETSI 119 602 LoTE / LoTL document from a Scheme row.

This is the Python port of `pb_hooks/_lib.js#buildEtsiLoTE` — same output
shape, same field naming conventions captured from the demo
output/<dir>/lote-EU.json files. The Go signer (when wired up) consumes
this JSON, adds ListIssueDateTime + NextUpdate, and signs.
"""
from __future__ import annotations

import re
from typing import Any

from .models import (
    Entity,
    ListType,
    LotlPointer,
    Scheme,
)


_PEM_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----"
)


def _split_pem_chain(pem: str | None) -> list[str]:
    if not pem:
        return []
    return [m.group(0).replace("\r\n", "\n").strip() for m in _PEM_RE.finditer(pem)]


def _pem_to_b64_der(pem: str) -> str:
    """Strip PEM armor + whitespace → naked base64 DER."""
    return (
        re.sub(r"-----BEGIN [^-]+-----", "", pem)
        .replace("-----END CERTIFICATE-----", "")
        .replace("\r", "")
        .replace("\n", "")
        .replace(" ", "")
        .strip()
    )


def _to_lang_value(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    return [
        {"lang": item.get("language") or item.get("lang") or "", "value": item.get("value", "")}
        for item in (items or [])
    ]


def _to_lang_uri(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    return [
        {
            "lang": item.get("language") or item.get("lang") or "",
            "uriValue": item.get("value") or item.get("uriValue") or "",
        }
        for item in (items or [])
    ]


def build_etsi_lote(scheme: Scheme) -> dict[str, Any]:
    """Produce the canonical ETSI 119 602 LoTE/LoTL JSON for `scheme`."""
    info: dict[str, Any] = {
        "LoTEVersionIdentifier": 1,
        "LoTESequenceNumber": scheme.sequence_number or 1,
        "LoTEType": scheme.scheme_type,
        "SchemeOperatorName": _to_lang_value(scheme.operator_names),
        "SchemeName": _to_lang_value(scheme.scheme_name),
        "SchemeTerritory": scheme.territory,
    }

    if scheme.is_lotl:
        pointers: list[LotlPointer] = list(
            scheme.lotl_pointers.order_by("scheme_territory", "scheme_type")
        )
        info["PointersToOtherLoTE"] = [
            {
                "LoTELocation": p.location,
                "ServiceDigitalIdentities": None,
                "LoTEQualifiers": [
                    {
                        "LoTEType": p.scheme_type,
                        "SchemeOperatorName": _to_lang_value(p.scheme_operator_names),
                        "SchemeTerritory": p.scheme_territory,
                        "MimeType": p.mime_type,
                    }
                ],
            }
            for p in pointers
        ]
        return {"LoTE": {"ListAndSchemeInformation": info}}

    is_pubeaa = scheme.list_type == ListType.PUBEAA

    entities = list(scheme.entities.order_by("entity_id"))
    trusted_entities = []
    for ent in entities:
        # ─── ServiceDigitalIdentity ───
        certs = [{"val": _pem_to_b64_der(p)} for p in _split_pem_chain(ent.cert_pem)]
        sdi: dict[str, Any] = {}
        if certs:
            sdi["X509Certificates"] = certs
        if ent.jwk and len(ent.jwk) > 0:
            sdi["PublicKeyValues"] = [ent.jwk]
        if ent.did_uri:
            sdi["OtherIds"] = [ent.did_uri]

        # ─── TEAddress ───
        address = ent.address or {}
        postal = (address.get("postal") or {}) if isinstance(address, dict) else {}
        electronic = address.get("electronic") if isinstance(address, dict) else None
        electronic = electronic if isinstance(electronic, list) else []

        te_address: dict[str, Any] = {}
        if any(postal.get(k) for k in ("streetAddress", "locality", "postalCode", "countryName")):
            te_address["TEPostalAddress"] = [
                {
                    "lang": "",
                    "StreetAddress": postal.get("streetAddress", ""),
                    "Locality": postal.get("locality", ""),
                    "PostalCode": postal.get("postalCode", ""),
                    "Country": postal.get("countryName", ""),
                }
            ]
        if electronic:
            te_address["TEElectronicAddress"] = [
                {"lang": "", "uriValue": uri} for uri in electronic
            ]

        # ─── TrustedEntityServices ───
        services_in = ent.services or []
        te_services = []
        for svc in services_in:
            svc_info: dict[str, Any] = {
                "ServiceName": _to_lang_value(svc.get("serviceNames")),
            }
            if sdi:
                svc_info["ServiceDigitalIdentity"] = sdi
            svc_info["ServiceTypeIdentifier"] = svc.get("serviceType", "")
            if is_pubeaa and svc.get("status"):
                svc_info["ServiceStatus"] = svc["status"]
            te_services.append({"ServiceInformation": svc_info})

        # ─── TrustedEntityInformation ───
        tei: dict[str, Any] = {"TEName": _to_lang_value(ent.names)}
        if te_address:
            tei["TEAddress"] = te_address
        if ent.information_uri:
            tei["TEInformationURI"] = _to_lang_uri(ent.information_uri)

        trusted_entities.append(
            {
                "TrustedEntityInformation": tei,
                "TrustedEntityServices": te_services,
            }
        )

    return {
        "LoTE": {
            "ListAndSchemeInformation": info,
            "TrustedEntitiesList": trusted_entities,
        }
    }
