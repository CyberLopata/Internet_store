import uuid
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from PIL import Image, ImageOps

MAX_UPLOAD_MB = 10
MAX_SIDE_PX = 1200
WEBP_QUALITY = 82


def product_image_storage():
    """Фото товарів лежать у static/images/ і віддаються за адресою /static/images/..."""
    return FileSystemStorage(
        location=settings.PRODUCT_IMAGES_DIR,
        base_url=settings.STATIC_URL + "images/",
    )


def validate_image_size(f):
    if f.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"Файл завеликий (максимум {MAX_UPLOAD_MB} МБ).")


def to_webp(uploaded, base_name):
    """Конвертує завантажене зображення у WebP, зменшуючи до MAX_SIDE_PX."""
    uploaded.seek(0)
    img = ImageOps.exif_transpose(Image.open(uploaded))
    img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=6)
    return ContentFile(buf.getvalue(), name=f"{base_name}-{uuid.uuid4().hex[:8]}.webp")


class Category(models.Model):
    name = models.CharField("Назва", max_length=120)
    slug = models.SlugField("Slug", unique=True)
    emoji = models.CharField("Емодзі", max_length=8, blank=True)
    parent = models.ForeignKey(
        "self", verbose_name="Батьківська категорія", null=True, blank=True,
        on_delete=models.CASCADE, related_name="children",
    )
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    in_menu = models.BooleanField("Показувати в меню", default=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog_category", args=[self.slug])

    def with_children_ids(self):
        return [self.pk, *self.children.values_list("pk", flat=True)]


class Product(models.Model):
    category = models.ForeignKey(
        Category, verbose_name="Категорія", on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField("Назва", max_length=200)
    slug = models.SlugField("Slug", unique=True)
    emoji = models.CharField("Емодзі", max_length=8, blank=True, default="🛍️")
    color = models.CharField("Колір фону картки", max_length=7, default="#e4e6ee")
    image = models.ImageField(
        "Фото", storage=product_image_storage, blank=True, validators=[validate_image_size],
        help_text="JPG, PNG, GIF або WebP до 10 МБ. Автоматично зберігається як WebP у static/images/.",
    )
    description = models.TextField("Опис", blank=True)
    price = models.DecimalField("Ціна", max_digits=10, decimal_places=2)
    old_price = models.DecimalField("Стара ціна", max_digits=10, decimal_places=2, null=True, blank=True)
    reviews_count = models.PositiveIntegerField("Кількість відгуків", default=0)
    is_active = models.BooleanField("Активний", default=True)
    is_hit = models.BooleanField("Хіт продажу", default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "name"]
        verbose_name = "Товар"
        verbose_name_plural = "Товари"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("product_detail", args=[self.slug])

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old_name = Product.objects.filter(pk=self.pk).values_list("image", flat=True).first()
        if self.image and not self.image._committed:  # завантажено новий файл
            webp = to_webp(self.image.file, self.slug)
            self.image.save(webp.name, webp, save=False)
        super().save(*args, **kwargs)
        if old_name and old_name != (self.image.name or ""):
            self.image.storage.delete(old_name)  # прибираємо старе фото

    def delete(self, *args, **kwargs):
        photos = list(self.photos.all())
        image = self.image
        super().delete(*args, **kwargs)
        for photo in photos:
            if photo.image:
                photo.image.storage.delete(photo.image.name)
        if image:
            image.storage.delete(image.name)

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return round((1 - self.price / self.old_price) * 100)
        return 0


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, verbose_name="Товар", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField(
        "Фото", storage=product_image_storage, validators=[validate_image_size],
        help_text="JPG, PNG, GIF або WebP до 10 МБ. Автоматично зберігається як WebP у static/images/.",
    )
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "Фото товару"
        verbose_name_plural = "Фото товару"

    def __str__(self):
        return f"{self.product.name} — фото {self.order + 1}"

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old_name = ProductImage.objects.filter(pk=self.pk).values_list("image", flat=True).first()
        if self.image and not self.image._committed:
            webp = to_webp(self.image.file, self.product.slug)
            self.image.save(webp.name, webp, save=False)
        super().save(*args, **kwargs)
        if old_name and old_name != (self.image.name or ""):
            self.image.storage.delete(old_name)

    def delete(self, *args, **kwargs):
        image = self.image
        super().delete(*args, **kwargs)
        if image:
            image.storage.delete(image.name)


class Review(models.Model):
    RATING_CHOICES = [(value, str(value)) for value in range(1, 6)]

    product = models.ForeignKey(
        Product, verbose_name="Товар", on_delete=models.CASCADE, related_name="reviews"
    )
    name = models.CharField("Ім'я", max_length=120)
    rating = models.PositiveSmallIntegerField("Оцінка", choices=RATING_CHOICES)
    text = models.TextField("Відгук")
    is_published = models.BooleanField("Опублікований", default=True)
    created = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        ordering = ["-created", "pk"]
        verbose_name = "Відгук"
        verbose_name_plural = "Відгуки"

    def __str__(self):
        return f"{self.product.name} — {self.name} ({self.rating}/5)"

    @property
    def stars(self):
        return "★" * self.rating + "☆" * (5 - self.rating)

    @staticmethod
    def _sync_product_count(product_id):
        count = Review.objects.filter(product_id=product_id, is_published=True).count()
        Product.objects.filter(pk=product_id).update(reviews_count=count)

    def save(self, *args, **kwargs):
        old_product_id = None
        if self.pk:
            old_product_id = Review.objects.filter(pk=self.pk).values_list("product_id", flat=True).first()
        super().save(*args, **kwargs)
        if old_product_id and old_product_id != self.product_id:
            self._sync_product_count(old_product_id)
        self._sync_product_count(self.product_id)

    def delete(self, *args, **kwargs):
        product_id = self.product_id
        super().delete(*args, **kwargs)
        self._sync_product_count(product_id)


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Нове"
        CONFIRMED = "confirmed", "Підтверджене"
        SHIPPED = "shipped", "Відправлене"
        DONE = "done", "Виконане"
        CANCELED = "canceled", "Скасоване"

    name = models.CharField("Ім'я", max_length=120)
    phone = models.CharField("Телефон", max_length=32)
    email = models.EmailField("Email", blank=True)
    city = models.CharField("Місто", max_length=120)
    address = models.CharField("Адреса / відділення", max_length=255)
    comment = models.TextField("Коментар", blank=True)
    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.NEW)
    total = models.DecimalField("Сума", max_digits=12, decimal_places=2, default=Decimal("0"))
    created = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Замовлення"
        verbose_name_plural = "Замовлення"

    def __str__(self):
        return f"Замовлення №{self.pk} — {self.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Позиція замовлення"
        verbose_name_plural = "Позиції замовлення"

    @property
    def subtotal(self):
        return self.price * self.quantity
