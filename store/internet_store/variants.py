"""Масове створення варіантів товару: розміри × кольори."""
import re

from .models import ProductVariant

MAX_COMBINATIONS = 200


def parse_list(text):
    """«39, 40; 41» -> ["39", "40", "41"]: без порожніх і дублів (без урахування регістру), порядок збережено."""
    seen, out = set(), []
    for part in re.split(r"[,;\n]+", text or ""):
        part = part.strip()
        if part and part.lower() not in seen:
            seen.add(part.lower())
            out.append(part)
    return out


def combinations(sizes, colors):
    """Усі пари (розмір, колір). Якщо задано лише одне з двох, друге порожнє."""
    if sizes and colors:
        return [(s, c) for c in colors for s in sizes]
    return [(s, "") for s in sizes] if sizes else [("", c) for c in colors]


def create_variants(product, sizes, colors, stock):
    """Створює відсутні варіанти. Повертає (створено, пропущено наявних)."""
    existing = {(v.size.lower(), v.color_name.lower()) for v in product.variants.all()}
    position = max([v.order for v in product.variants.all()], default=-1) + 1
    created = skipped = 0
    for size, color in combinations(sizes, colors):
        if (size.lower(), color.lower()) in existing:
            skipped += 1
            continue
        ProductVariant.objects.create(product=product, size=size, color_name=color, stock=stock, order=position)
        position += 1
        created += 1
    return created, skipped
