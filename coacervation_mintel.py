"""
Mintel GNPD connector for the coacervation product catalog.

Pulls ingredient lists, claims/positioning and a product image for competitor /
in-market shampoos, so the Product catalog can be enriched from Mintel instead of
manual copy-paste.  Follows the same safe pattern as ``coacervation_nexus.py``:
``status()`` never opens a connection, and everything degrades gracefully when
unconfigured.

IMPORTANT - this module is intentionally *configuration-driven* because Mintel's
API contract (base URL, auth scheme, JSON field names) depends on your specific
subscription and is not hard-coded here.  Fill these in ``.env`` and it goes live
with no code changes:

    MINTEL_API_BASE=https://<your-mintel-api-host>
    MINTEL_AUTH_MODE=bearer            # bearer | apikey | oauth2
    MINTEL_API_KEY=...                 # for bearer/apikey
    MINTEL_AUTH_HEADER=Authorization   # header name for apikey mode
    # oauth2 (client-credentials) only:
    MINTEL_CLIENT_ID=...
    MINTEL_CLIENT_SECRET=...
    MINTEL_TOKEN_URL=https://<host>/oauth/token
    # endpoint templates ({gtin} / {query} are substituted):
    MINTEL_GTIN_ENDPOINT=/v1/products?gtin={gtin}
    MINTEL_SEARCH_ENDPOINT=/v1/products?search={query}
    # response field paths (dot notation; first list element auto-picked):
    MINTEL_RESULT_PATH=products
    MINTEL_FIELD_NAME=product_name
    MINTEL_FIELD_BRAND=brand
    MINTEL_FIELD_INGREDIENTS=ingredients
    MINTEL_FIELD_CLAIMS=claims
    MINTEL_FIELD_IMAGE=image_url

Server-safety: also honours the corporate DNS override in ``databricks_template``
if present, and returns a clear error (never hangs) if the Mintel host is not
reachable through the network gateway.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*_a, **_k):  # type: ignore
        return False


def _load_env() -> None:
    load_dotenv()
    for p in (Path.cwd(), Path(__file__).resolve().parent):
        env = p / ".env"
        if env.exists():
            load_dotenv(env)


def _cfg(key: str, default: str = "") -> str:
    _load_env()
    return (os.getenv(key) or default).strip()


def status() -> dict[str, Any]:
    """Readiness report - does NOT open a connection."""
    base = _cfg("MINTEL_API_BASE")
    mode = _cfg("MINTEL_AUTH_MODE", "bearer").lower()
    if mode == "oauth2":
        has_creds = bool(_cfg("MINTEL_CLIENT_ID") and _cfg("MINTEL_CLIENT_SECRET")
                         and _cfg("MINTEL_TOKEN_URL"))
    else:
        has_creds = bool(_cfg("MINTEL_API_KEY"))
    return {
        "package_installed": requests is not None,
        "auth_mode": mode,
        "has_base_url": bool(base),
        "has_credentials": has_creds,
        "gtin_endpoint": _cfg("MINTEL_GTIN_ENDPOINT"),
        "search_endpoint": _cfg("MINTEL_SEARCH_ENDPOINT"),
        "ready": bool(requests is not None and base and has_creds
                      and (_cfg("MINTEL_GTIN_ENDPOINT") or _cfg("MINTEL_SEARCH_ENDPOINT"))),
    }


def _dns_override() -> None:
    root = Path(__file__).resolve().parent
    for cand in (root, root.parent):
        if (cand / "databricks_template.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            try:
                import databricks_template as t  # type: ignore
                dns = getattr(t, "DNS_OVERRIDE", None)
                if dns:
                    import socket
                    try:
                        socket.gethostbyname(dns["hostname"])
                    except socket.gaierror:
                        t.apply_dns_override()
            except Exception:
                pass
            break


def _auth_headers() -> dict[str, str]:
    mode = _cfg("MINTEL_AUTH_MODE", "bearer").lower()
    if mode == "oauth2":
        token = _oauth_token()
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    key = _cfg("MINTEL_API_KEY")
    if not key:
        raise RuntimeError("MINTEL_API_KEY not set.")
    if mode == "apikey":
        header = _cfg("MINTEL_AUTH_HEADER", "Authorization")
        return {header: key, "Accept": "application/json"}
    # default: bearer
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def _oauth_token() -> str:
    cid = _cfg("MINTEL_CLIENT_ID")
    secret = _cfg("MINTEL_CLIENT_SECRET")
    token_url = _cfg("MINTEL_TOKEN_URL")
    if not (cid and secret and token_url):
        raise RuntimeError("OAuth2 mode needs MINTEL_CLIENT_ID/SECRET/TOKEN_URL.")
    resp = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "client_id": cid, "client_secret": secret,
    }, timeout=30)
    _reject_if_not_json(resp)
    return resp.json().get("access_token", "")


def _reject_if_not_json(resp) -> None:
    """Raise a clear error if a gateway/login page came back instead of JSON."""
    ctype = resp.headers.get("Content-Type", "")
    host = ""
    try:
        host = requests.utils.urlparse(resp.url).netloc
    except Exception:
        pass
    if "zscaler" in host or "gateway" in host:
        raise RuntimeError(
            f"Request was intercepted by the network gateway ({host}). The Mintel "
            "host must be allow-listed through Zscaler for server-side access.")
    if "json" not in ctype.lower():
        raise RuntimeError(
            f"Expected JSON from Mintel but got '{ctype or 'unknown'}' (status "
            f"{resp.status_code}). Check MINTEL_API_BASE / endpoint / auth.")


def _dig(obj: Any, dotpath: str) -> Any:
    """Traverse a nested dict/list by a dotted path; first list element is used."""
    if not dotpath:
        return None
    cur = obj
    for part in dotpath.split("."):
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x)
    return str(v)


def _request(endpoint: str) -> dict:
    base = _cfg("MINTEL_API_BASE")
    if not base:
        raise RuntimeError("MINTEL_API_BASE not set.")
    if requests is None:
        raise RuntimeError("requests is not installed.")
    _dns_override()
    url = base.rstrip("/") + "/" + endpoint.lstrip("/")
    resp = requests.get(url, headers=_auth_headers(), timeout=30)
    _reject_if_not_json(resp)
    return resp.json()


def _normalize(record: Any) -> dict[str, Any]:
    return {
        "name": _as_text(_dig(record, _cfg("MINTEL_FIELD_NAME", "product_name"))),
        "brand": _as_text(_dig(record, _cfg("MINTEL_FIELD_BRAND", "brand"))),
        "ingredients": _as_text(_dig(record, _cfg("MINTEL_FIELD_INGREDIENTS", "ingredients"))),
        "claims": _as_text(_dig(record, _cfg("MINTEL_FIELD_CLAIMS", "claims"))),
        "image": _as_text(_dig(record, _cfg("MINTEL_FIELD_IMAGE", "image_url"))),
    }


def lookup_gtin(gtin: str) -> dict[str, Any]:
    ep = _cfg("MINTEL_GTIN_ENDPOINT")
    if not ep:
        raise RuntimeError("MINTEL_GTIN_ENDPOINT not configured.")
    data = _request(ep.replace("{gtin}", str(gtin).strip()))
    result_path = _cfg("MINTEL_RESULT_PATH")
    record = _dig(data, result_path) if result_path else data
    out = _normalize(record if record is not None else data)
    out["source"] = "mintel:gtin"
    out["query"] = gtin
    return out


def search(name: str) -> dict[str, Any]:
    ep = _cfg("MINTEL_SEARCH_ENDPOINT")
    if not ep:
        raise RuntimeError("MINTEL_SEARCH_ENDPOINT not configured.")
    from urllib.parse import quote
    data = _request(ep.replace("{query}", quote(str(name).strip())))
    result_path = _cfg("MINTEL_RESULT_PATH")
    record = _dig(data, result_path) if result_path else data
    out = _normalize(record if record is not None else data)
    out["source"] = "mintel:search"
    out["query"] = name
    return out
