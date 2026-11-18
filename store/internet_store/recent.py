"""Нещодавно переглянуті товари: список id у сесії (найновіші першими)."""
from .models import Product

SESSION_KEY = "recent"
MAX_STORED = 12


def _ids(request):
    return [i for i in request.session.get(SESSION_KEY, []) if isinstance(i, int)]


def remember(request, product):
    ids = _ids(request)
    if ids and ids[0] == product.pk:
        return  # той самий товар підряд: сесію не чіпаємо
    ids = [i for i in ids if i != product.pk]
    request.session[SESSION_KEY] = [product.pk] + ids[:MAX_STORED - 1]


def recent_products(request, exclude=None, limit=6):
    """Активні товари з історії, найновіші першими; видалені й вимкнені пропускаються."""
    ids = [i for i in _ids(request) if i != exclude]
    if not ids:
        return []
    by_id = {p.pk: p for p in Product.objects.filter(pk__in=ids, is_active=True)
             .select_related("category").prefetch_related("variants")}
    return [by_id[i] for i in ids if i in by_id][:limit]


def clear(request):
    request.session.pop(SESSION_KEY, None)
