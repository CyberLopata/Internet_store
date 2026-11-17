from decimal import Decimal

from .models import Product, ProductVariant

SESSION_KEY = "cart"
MAX_QTY = 99


def make_key(product, variant=None):
    """Ключ позиції в кошику: "12" (товар без варіантів) або "12:5" (товар 12, варіант 5)."""
    return f"{product.pk}:{variant.pk}" if variant else str(product.pk)


def _parse(key):
    pid, _, vid = str(key).partition(":")
    if not pid.isdigit() or (vid and not vid.isdigit()):
        return None
    return int(pid), (int(vid) if vid else None)


class Cart:
    """Кошик у сесії: {ключ: кількість}."""

    def __init__(self, request):
        self.session = request.session
        self.data = self.session.setdefault(SESSION_KEY, {})

    def _save(self):
        self.session.modified = True

    def add(self, product, qty=1, variant=None):
        """Додає товар; не більше залишку варіанта. Повертає кількість у кошику після додавання."""
        key = make_key(product, variant)
        limit = min(MAX_QTY, variant.stock) if variant else MAX_QTY
        self.data[key] = min(self.data.get(key, 0) + qty, limit)
        self._save()
        return self.data[key]

    def set(self, key, qty):
        key = str(key)
        if qty <= 0:
            self.data.pop(key, None)
        elif key in self.data:
            parsed = _parse(key)
            limit = MAX_QTY
            if parsed and parsed[1]:
                stock = ProductVariant.objects.filter(pk=parsed[1]).values_list("stock", flat=True).first()
                limit = min(MAX_QTY, stock or 0)
            if limit <= 0:
                self.data.pop(key, None)
            else:
                self.data[key] = min(qty, limit)
        self._save()

    def remove(self, key):
        self.data.pop(str(key), None)
        self._save()

    def clear(self):
        self.session.pop(SESSION_KEY, None)
        self.session.modified = True

    def __len__(self):
        return sum(self.data.values())

    def items(self):
        parsed = {k: _parse(k) for k in self.data}
        for k in [k for k, v in parsed.items() if v is None]:  # зіпсований ключ
            del self.data[k]
        parsed = {k: v for k, v in parsed.items() if v is not None}

        products = {p.pk: p for p in Product.objects.filter(pk__in={p for p, _ in parsed.values()}, is_active=True)}
        variants = {v.pk: v for v in ProductVariant.objects.filter(
            pk__in={v for _, v in parsed.values() if v}, is_active=True)}
        with_variants = set(ProductVariant.objects.filter(
            product_id__in=products, is_active=True).values_list("product_id", flat=True))

        result = []
        for key, (pid, vid) in parsed.items():
            product = products.get(pid)
            variant = variants.get(vid) if vid else None
            qty = self.data[key]
            limited = False
            # товар вимкнули/видалили, варіант зник або розпродано, або в товару з'явились варіанти — прибираємо
            if (product is None or (vid and (variant is None or variant.product_id != pid or variant.stock <= 0))
                    or (not vid and pid in with_variants)):
                del self.data[key]
                continue
            if variant and qty > variant.stock:
                qty = self.data[key] = variant.stock
                limited = True
            unit = variant.effective_price if variant else product.price
            result.append({
                "key": key, "product": product, "variant": variant, "quantity": qty, "limited": limited,
                "unit_price": unit, "subtotal": unit * qty,
                "label": variant.label if variant else "",
                "max": variant.stock if variant else MAX_QTY,
            })
        self._save()
        return iter(result)

    @property
    def total(self):
        return sum((i["subtotal"] for i in self.items()), Decimal("0"))
