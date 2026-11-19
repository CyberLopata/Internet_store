"""Пошук товарів: усі слова запиту мають зустрітися в назві, описі або назві категорії."""
from django.db import connection
from django.db.models import Q

MAX_WORDS = 6
SUGGEST_LIMIT = 6


def words(query):
    seen, out = set(), []
    for w in (query or "").split():
        key = w.casefold()
        if key not in seen:
            seen.add(key)
            out.append(w)
    return out[:MAX_WORDS]


def search_products(qs, query):
    """Фільтрує queryset товарів за запитом (без урахування регістру, також для кирилиці)."""
    ws = words(query)
    if not ws:
        return qs
    if connection.vendor == "sqlite":
        # LIKE в SQLite ігнорує регістр лише для ASCII, тож для кирилиці порівнюємо в Python (це режим розробки).
        folded = [w.casefold() for w in ws]
        ids = []
        for p in qs.select_related("category"):
            text = " ".join((p.name, p.description or "", p.category.name)).casefold()
            if all(w in text for w in folded):
                ids.append(p.pk)
        return qs.filter(pk__in=ids)
    for w in ws:
        qs = qs.filter(Q(name__icontains=w) | Q(description__icontains=w) | Q(category__name__icontains=w))
    return qs


def relevance(product, query):
    """Менше = краще: назва починається із запиту, потім слово в назві починається із запиту, потім збіг у назві."""
    name = product.name.casefold()
    q = (query or "").strip().casefold()
    if name.startswith(q):
        return 0
    ws = [w.casefold() for w in words(query)]
    parts = name.replace("«", " ").replace("»", " ").split()
    if ws and all(any(part.startswith(w) for part in parts) for w in ws):
        return 1
    if all(w in name for w in ws):
        return 2
    return 3


def suggest(qs, query, limit=SUGGEST_LIMIT):
    """(список для підказок, загальна кількість збігів). Спершу найрелевантніші, далі ті, що в наявності."""
    matches = list(search_products(qs, query).select_related("category").prefetch_related("variants")[:200])
    matches.sort(key=lambda p: (relevance(p, query), not p.in_stock, p.name.casefold()))
    return matches[:limit], len(matches)
