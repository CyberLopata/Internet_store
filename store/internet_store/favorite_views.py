from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from . import favorites
from .models import Product
from .views import _back, _is_ajax


@require_POST
def favorite_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    active = favorites.toggle(request, product)
    if _is_ajax(request):
        return JsonResponse({"active": active, "count": len(favorites.favorite_ids(request))})
    return _back(request, fallback="favorites")


def favorites_page(request):
    ids = favorites.favorite_ids(request)
    by_id = {p.pk: p for p in Product.objects.filter(pk__in=ids, is_active=True)
             .select_related("category").prefetch_related("variants")}
    return render(request, "favorites.html", {"products": [by_id[i] for i in ids if i in by_id]})
