from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Product
from .search import suggest

MIN_LEN = 2


def _price(value):
    return f"{int(value):,}".replace(",", " ") + " ₴"


@require_GET
def search_suggest(request):
    q = request.GET.get("q", "").strip()[:80]
    if len(q) < MIN_LEN:
        return JsonResponse({"q": q, "total": 0, "results": []})
    products, total = suggest(Product.objects.filter(is_active=True), q)
    return JsonResponse({
        "q": q,
        "total": total,
        "results": [{
            "name": p.name,
            "url": p.get_absolute_url(),
            "price": _price(p.price),
            "old_price": _price(p.old_price) if p.old_price and p.old_price > p.price else "",
            "image": p.image.url if p.image else "",
            "emoji": p.emoji or "",
            "color": p.color or "",
            "category": p.category.name,
            "in_stock": p.in_stock,
        } for p in products],
    })
