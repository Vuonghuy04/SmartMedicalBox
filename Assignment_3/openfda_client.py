import hashlib
import json
import re

import requests

from medicine_config import (
    OPENFDA_API_KEY,
    OPENFDA_BASE_URL,
    OPENFDA_TIMEOUT_SECONDS,
)


class OpenFDAError(Exception):
    pass


def _clean_query(query):
    cleaned = re.sub(r"[^A-Za-z0-9 .'-]", " ", query or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise OpenFDAError("Enter a medicine name to search.")
    return cleaned


def _first(value, default=""):
    if isinstance(value, list):
        return str(value[0]) if value else default
    if value is None:
        return default
    return str(value)


def _join(value, limit=5):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:limit])
    if value is None:
        return ""
    return str(value)


def _text(record, keys):
    for key in keys:
        value = record.get(key)
        if value:
            return _join(value, limit=2)
    return ""


def _fingerprint(record):
    seed = json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def normalize_record(record):
    openfda = record.get("openfda", {})
    brand = _first(openfda.get("brand_name")) or _first(record.get("brand_name"))
    generic = _first(openfda.get("generic_name"))
    source_id = record.get("set_id") or record.get("id") or _fingerprint(record)

    return {
        "source_id": source_id,
        "brand_name": brand or generic or "Unknown medicine",
        "generic_name": generic,
        "manufacturer": _first(openfda.get("manufacturer_name")),
        "product_type": _first(openfda.get("product_type")),
        "route": _join(openfda.get("route")),
        "substance_name": _join(openfda.get("substance_name")),
        "purpose": _text(record, ["purpose", "indications_and_usage"]),
        "warnings": _text(record, ["boxed_warning", "warnings", "warnings_and_cautions"]),
        "dosage_and_administration": _text(record, ["dosage_and_administration"]),
    }


def _search_expressions(query):
    if " " in query:
        quoted = f'"{query}"'
        return [
            f"openfda.brand_name:{quoted}",
            f"openfda.generic_name:{quoted}",
            f"openfda.substance_name:{quoted}",
        ]

    return [
        f"openfda.brand_name:{query}*",
        f"openfda.generic_name:{query}*",
        f"openfda.substance_name:{query}*",
    ]


def _fetch(search, limit):
    params = {"search": search, "limit": limit}
    if OPENFDA_API_KEY:
        params["api_key"] = OPENFDA_API_KEY

    response = requests.get(
        OPENFDA_BASE_URL,
        params=params,
        timeout=OPENFDA_TIMEOUT_SECONDS,
    )
    if response.status_code == 404:
        return []
    if response.status_code >= 400:
        raise OpenFDAError(
            f"openFDA request failed with HTTP {response.status_code}: {response.text[:200]}"
        )
    return response.json().get("results", [])


def search_medicines(query, limit=8):
    query = _clean_query(query)
    seen = set()
    results = []

    for expression in _search_expressions(query):
        for record in _fetch(expression, limit):
            normalized = normalize_record(record)
            key = (
                normalized["source_id"],
                normalized["brand_name"].lower(),
                normalized["generic_name"].lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized["source_json"] = json.dumps(normalized, default=str)
            results.append(normalized)
            if len(results) >= limit:
                return results

    return results
