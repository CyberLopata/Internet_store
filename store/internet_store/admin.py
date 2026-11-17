from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Max
from django.utils.html import format_html

from .models import Category, ChatMessage, ChatThread, Order, OrderItem, Product, ProductImage, ProductVariant, Profile, Review, validate_image_size

User = get_user_model()


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Поле для вибору кількох зображень одразу (див. документацію Django про multiple files)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(d, initial) for d in data if d]
        return [clean_one(data, initial)] if data else []


class ProductAdminForm(forms.ModelForm):
    extra_photos = MultipleImageField(
        label="Додаткові фото (можна вибрати кілька)", required=False,
        validators=[validate_image_size],
        help_text="Зажміть Ctrl/Shift (Cmd на Mac), щоб вибрати одразу кілька файлів. "
                  "Головне фото вище показується в каталозі, додаткові — в галереї на сторінці товару.",
    )

    class Meta:
        model = Product
        fields = "__all__"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("size", "color_name", "color_hex", "stock", "price", "is_active", "order")

    class Media:
        js = ("js/admin_variant_color.js",)  # віконце вибору кольору поруч із текстовим полем


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ("preview", "image", "order")
    readonly_fields = ("preview",)

    @admin.display(description="Перегляд")
    def preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="height:64px;border-radius:6px">', obj.image.url)
        return "—"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "order", "in_menu")
    list_editable = ("order", "in_menu")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    inlines = [ProductVariantInline, ProductImageInline]
    list_display =("preview", "name", "category", "price", "old_price", "is_hit", "is_active")
    list_display_links = ("preview", "name")
    readonly_fields = ("preview",)

    @admin.display(description="Фото")
    def preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:48px;border-radius:6px">', obj.image.url)
        return "—"

    list_filter = ("category", "is_hit", "is_active")
    list_editable = ("price", "old_price", "is_hit", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        product = form.instance
        last = product.photos.aggregate(m=Max("order"))["m"]
        position = 0 if last is None else last + 1
        for photo in form.cleaned_data.get("extra_photos", []):
            ProductImage.objects.create(product=product, image=photo, order=position)
            position += 1


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "variant_label", "price", "quantity")
    fields = ("product", "product_name", "variant_label", "price", "quantity")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "city", "address", "user", "total", "status", "created")
    list_filter = ("status", "created")
    list_editable = ("status",)
    search_fields = ("name", "phone", "email", "user__email")
    raw_id_fields = ("user",)
    inlines = [OrderItemInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("created", "product", "name", "rating", "short_text", "is_published")
    list_display_links = ("created", "product")
    list_editable = ("is_published",)
    list_filter = ("is_published", "rating", "created")
    search_fields = ("name", "text", "product__name")
    autocomplete_fields = ("product",)
    date_hierarchy = "created"

    @admin.display(description="Текст")
    def short_text(self, obj):
        return obj.text if len(obj.text) <= 60 else obj.text[:57] + "…"


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "Профіль покупця"


admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "date_joined")
    inlines = [ProfileInline]

    def get_inline_instances(self, request, obj=None):
        # На сторінці створення профіль додається автоматично (сигналом), тому вбудовану форму не показуємо.
        return super().get_inline_instances(request, obj) if obj else []


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("created",)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "updated")
    raw_id_fields = ("user",)
    inlines = [ChatMessageInline]
