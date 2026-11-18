"""Обране: для залогінених у БД, для гостей у сесії (після входу гостьове обране зливається в акаунт)."""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import Favorite, Product

SESSION_KEY = "favorites"
MAX_GUEST = 100


def favorite_ids(request):
    """Впорядкований (найновіші першими) список id активних товарів в обраному."""
    if request.user.is_authenticated:
        return list(Favorite.objects.filter(user=request.user, product__is_active=True).values_list("product_id", flat=True))
    ids = [i for i in request.session.get(SESSION_KEY, []) if isinstance(i, int)]
    if not ids:
        return []
    active = set(Product.objects.filter(pk__in=ids, is_active=True).values_list("pk", flat=True))
    return [i for i in ids if i in active]


def toggle(request, product):
    """Додає/прибирає товар. Повертає True, якщо тепер він в обраному."""
    if request.user.is_authenticated:
        obj, created = Favorite.objects.get_or_create(user=request.user, product=product)
        if not created:
            obj.delete()
        return created
    ids = [i for i in request.session.get(SESSION_KEY, []) if isinstance(i, int)]
    added = product.pk not in ids
    if added:
        ids.insert(0, product.pk)
    else:
        ids.remove(product.pk)
    request.session[SESSION_KEY] = ids[:MAX_GUEST]
    return added


@receiver(user_logged_in)
def merge_guest_favorites(sender, request, user, **kwargs):
    """Те, що гість додав до обраного до входу, переходить в акаунт."""
    if request is None:
        return
    ids = [i for i in request.session.get(SESSION_KEY, []) if isinstance(i, int)]
    if not ids:
        return
    valid = Product.objects.filter(pk__in=ids).values_list("pk", flat=True)
    Favorite.objects.bulk_create([Favorite(user=user, product_id=pk) for pk in valid], ignore_conflicts=True)
    request.session.pop(SESSION_KEY, None)
