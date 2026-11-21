"""Бізнес-логіка, спільна для HTML-сайту і REST API."""
from django.db import transaction

from .models import OrderItem, ProductVariant, get_profile


class OutOfStock(Exception):
    """Залишок варіанта менший за кількість у кошику."""


def place_order(order, items, user=None):
    """Зберігає замовлення, його позиції і списує залишки. Працює в одній транзакції.

    order  — незбережений екземпляр Order (з полів форми або серіалізатора);
    items  — результат list(Cart.items());
    user   — покупець (або None для гостя).
    """
    with transaction.atomic():
        locked = {v.pk: v for v in ProductVariant.objects.select_for_update().filter(
            pk__in=[i["variant"].pk for i in items if i["variant"]])}
        for i in items:
            if i["variant"]:
                fresh = locked.get(i["variant"].pk)
                if fresh is None or fresh.stock < i["quantity"]:
                    raise OutOfStock(f"«{i['product'].name} ({i['label']})» уже немає в потрібній кількості.")
        if user is not None and user.is_authenticated:
            order.user = user
        order.total = sum(i["subtotal"] for i in items)
        order.save()
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=i["product"], variant=i["variant"], variant_label=i["label"],
                      product_name=i["product"].name, price=i["unit_price"], quantity=i["quantity"])
            for i in items
        ])
        for i in items:
            if i["variant"]:
                fresh = locked[i["variant"].pk]
                fresh.stock -= i["quantity"]
                fresh.save(update_fields=["stock"])
    return order


def remember_delivery(user, order):
    """Запам'ятовує телефон і адресу в профілі, якщо там ці поля ще порожні."""
    profile = get_profile(user)
    changed = []
    for field in ("phone", "city", "address"):
        if not getattr(profile, field) and getattr(order, field):
            setattr(profile, field, getattr(order, field))
            changed.append(field)
    if changed:
        profile.save(update_fields=changed)