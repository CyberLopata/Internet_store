from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import novaposhta


def _run(fn, *args):
    if not novaposhta.enabled():
        return JsonResponse({"enabled": False, "results": []}, status=404)
    try:
        return JsonResponse({"enabled": True, "results": fn(*args)})
    except novaposhta.NovaPoshtaError:
        return JsonResponse({"enabled": True, "error": "unavailable", "results": []}, status=503)


@require_GET
def np_cities(request):
    return _run(novaposhta.search_cities, request.GET.get("q", ""))


@require_GET
def np_warehouses(request):
    return _run(novaposhta.search_warehouses, request.GET.get("city", ""), request.GET.get("q", ""))
