"""Довідники Нової пошти: пошук міст і відділень (БЕЗ створення ТТН).

Працює лише якщо в налаштуваннях задано NOVA_POSHTA_API_KEY. Відповіді кешуються,
помилки мережі/API перетворюються на NovaPoshtaError (вітрина тоді просто
показує звичайні поля для ручного введення).
"""
import hashlib
import json
import logging
import urllib.request

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

API_URL = "https://api.novaposhta.ua/v2.0/json/"
TIMEOUT = 6
CACHE_TTL = 60 * 60 * 24
MIN_LEN = 2
CITY_LIMIT = 15
WH_LIMIT = 50


class NovaPoshtaError(Exception):
    pass


def enabled():
    return bool(getattr(settings, "NOVA_POSHTA_API_KEY", ""))


def _call(model, method, props):
    payload = json.dumps({
        "apiKey": getattr(settings, "NOVA_POSHTA_API_KEY", ""),
        "modelName": model,
        "calledMethod": method,
        "methodProperties": props,
    }).encode()
    req = urllib.request.Request(API_URL, payload, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # мережа, таймаут, не-JSON
        log.warning("Nova Poshta %s/%s failed: %s", model, method, exc)
        raise NovaPoshtaError(str(exc)) from exc
    if not isinstance(data, dict) or not data.get("success"):
        errors = data.get("errors") if isinstance(data, dict) else None
        raise NovaPoshtaError(str(errors or "bad response"))
    return data.get("data") or []


def _cached(key, fn):
    key = "np:" + hashlib.md5(key.encode()).hexdigest()
    hit = cache.get(key)
    if hit is not None:
        return hit
    value = fn()
    cache.set(key, value, CACHE_TTL)
    return value


def search_cities(query):
    q = (query or "").strip()[:60]
    if len(q) < MIN_LEN or not enabled():
        return []

    def load():
        data = _call("Address", "searchSettlements", {"CityName": q, "Limit": CITY_LIMIT, "Page": 1})
        out = []
        for block in data:
            for a in (block.get("Addresses") or []) if isinstance(block, dict) else []:
                ref = a.get("DeliveryCity")
                if not ref or not a.get("Warehouses"):
                    continue  # населені пункти без відділень нам не підходять
                out.append({
                    "ref": ref,
                    "name": a.get("MainDescription") or "",
                    "present": a.get("Present") or a.get("MainDescription") or "",
                })
        return out

    return _cached(f"c:{q.casefold()}", load)


def search_warehouses(city_ref, query=""):
    ref = (city_ref or "").strip()[:64]
    q = (query or "").strip()[:60]
    if not ref or not enabled():
        return []

    def load():
        props = {"CityRef": ref, "Limit": WH_LIMIT, "Page": 1, "Language": "UA"}
        if q:
            props["FindByString"] = q
        data = _call("Address", "getWarehouses", props)
        return [{
            "ref": w.get("Ref") or "",
            "number": str(w.get("Number") or ""),
            "name": w.get("Description") or "",
        } for w in data if isinstance(w, dict) and w.get("Description")]

    return _cached(f"w:{ref}:{q.casefold()}", load)
