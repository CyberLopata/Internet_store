"""Серіалізатори REST API: перетворюють моделі та кошик у JSON і перевіряють вхідні дані."""
from rest_framework import serializers

from ..cart import MAX_QTY
from ..models import Category, Order, OrderItem, Product, Review, ReviewPhoto


def absolute(request, url):
    """/static/images/a.webp -> https://site/static/images/a.webp"""
    if not url:
        return None
    return request.build_absolute_uri(url) if request else url


# ───────────────────────── Каталог ─────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    parent = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "emoji", "parent", "children"]

    def get_children(self, obj):
        return [{"id": c.pk, "name": c.name, "slug": c.slug, "emoji": c.emoji} for c in obj.children.all()]


class VariantSerializer(serializers.Serializer):
    """Варіант товару (розмір/колір) з власним залишком і ціною."""
    id = serializers.IntegerField(source="pk")
    size = serializers.CharField()
    color = serializers.CharField(source="color_name")
    color_hex = serializers.CharField()
    stock = serializers.IntegerField()
    in_stock = serializers.SerializerMethodField()
    price = serializers.DecimalField(source="effective_price", max_digits=10, decimal_places=2)

    def get_in_stock(self, v):
        return v.stock > 0


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    image = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    colors = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "price", "old_price", "discount_percent",
                  "image", "is_hit", "in_stock", "reviews_count", "colors"]

    def get_image(self, obj):
        return absolute(self.context.get("request"), obj.image.url if obj.image else "")

    def get_colors(self, obj):
        return list(dict.fromkeys(v.color_name for v in obj.active_variants if v.color_name))


class ReviewPhotoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = ReviewPhoto
        fields = ["id", "image"]

    def get_image(self, obj):
        return absolute(self.context.get("request"), obj.image.url)


class ReviewSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    # Приманка для ботів, як і на сайті: людина це поле не заповнює.
    website = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Review
        fields = ["id", "name", "rating", "text", "created", "photos", "website"]
        read_only_fields = ["id", "created", "photos"]

    def get_photos(self, obj):
        photos = getattr(obj, "approved_photos", None) or []  # лише схвалені модератором
        return ReviewPhotoSerializer(photos, many=True, context=self.context).data

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Оцінка від 1 до 5.")
        return value


class ProductDetailSerializer(ProductListSerializer):
    """Повна картка товару: опис, галерея (загальна і по кольорах), варіанти, підсумок відгуків."""
    description = serializers.CharField()
    gallery = serializers.SerializerMethodField()
    gallery_colors = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    reviews_total = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description", "gallery", "gallery_colors", "variants", "rating_avg", "reviews_total"]

    def _photos(self, obj):
        return [p for p in obj.photos.all() if p.image]

    def get_gallery(self, obj):
        req = self.context.get("request")
        urls = ([obj.image.url] if obj.image else []) + [p.image.url for p in self._photos(obj) if not p.color]
        return [absolute(req, u) for u in urls]

    def get_gallery_colors(self, obj):
        req = self.context.get("request")
        photos = self._photos(obj)
        out = {}
        for name in dict.fromkeys(v.color_name for v in obj.active_variants if v.color_name):
            urls = [absolute(req, p.image.url) for p in photos if p.color.lower() == name.lower()]
            if urls:
                out[name] = urls
        return out

    def get_variants(self, obj):
        return VariantSerializer(obj.active_variants, many=True).data

    def get_rating_avg(self, obj):
        avg = getattr(obj, "rating_avg", None)
        return round(avg, 1) if avg is not None else None

    def get_reviews_total(self, obj):
        return getattr(obj, "reviews_total", 0)


# ───────────────────────── Кошик ─────────────────────────

class CartItemSerializer(serializers.Serializer):
    """Позиція кошика (елемент, який повертає Cart.items())."""
    key = serializers.CharField()
    product = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()
    label = serializers.CharField()
    image = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()
    max = serializers.IntegerField()
    limited = serializers.BooleanField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)

    def get_product(self, i):
        return {"id": i["product"].pk, "name": i["product"].name, "slug": i["product"].slug}

    def get_variant(self, i):
        v = i["variant"]
        return {"id": v.pk, "size": v.size, "color": v.color_name} if v else None

    def get_image(self, i):
        return absolute(self.context.get("request"), i["image_url"])


class CartAddSerializer(serializers.Serializer):
    product = serializers.IntegerField(min_value=1)
    variant = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QTY, default=1)

    def validate(self, data):
        product = Product.objects.filter(pk=data["product"], is_active=True).first()
        if product is None:
            raise serializers.ValidationError({"product": "Товар не знайдено."})
        options = product.active_variants
        variant = None
        if options:  # для товару з варіантами розмір/колір обов'язкові
            variant = next((v for v in options if v.pk == data.get("variant")), None)
            if variant is None:
                raise serializers.ValidationError({"variant": "Оберіть розмір і колір (id варіанта з картки товару)."})
            if variant.stock <= 0:
                raise serializers.ValidationError({"variant": "Цього варіанту немає в наявності."})
        elif data.get("variant"):
            raise serializers.ValidationError({"variant": "У цього товару немає варіантів."})
        data["product_obj"], data["variant_obj"] = product, variant
        return data


class CartUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0, max_value=MAX_QTY, help_text="0 — видалити позицію")


# ───────────────────────── Замовлення ─────────────────────────

class OrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name")
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        model = OrderItem
        fields = ["product", "name", "variant_label", "price", "quantity", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "status_display", "name", "phone", "email", "city", "address",
                  "comment", "total", "created", "items"]


class CheckoutSerializer(serializers.ModelSerializer):
    """Дані доставки для оформлення замовлення з кошика."""

    class Meta:
        model = Order
        fields = ["name", "phone", "email", "city", "address", "comment"]