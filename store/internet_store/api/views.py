"""Представлення REST API (префікс /api/)."""
from decimal import Decimal

from django.db.models import Avg, Count, F, Prefetch, Q
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ..cart import Cart
from ..models import Category, Order, Product, ReviewPhoto
from ..search import search_products
from ..services import OutOfStock, place_order, remember_delivery
from .serializers import (CartAddSerializer, CartItemSerializer, CartUpdateSerializer, CategorySerializer,
                          CheckoutSerializer, OrderSerializer, ProductDetailSerializer,
                          ProductListSerializer, ReviewSerializer)


class ApiRoot(APIView):
    """Корінь API: перелік основних адрес."""

    def get(self, request):
        r = lambda name, **kw: reverse(name, request=request, **kw)  # noqa: E731
        return Response({
            "categories": r("api:category-list"),
            "products": r("api:product-list"),
            "cart": r("api:cart"),
            "checkout": r("api:checkout"),
            "orders": r("api:order-list"),
            "token": r("api:token"),
        })


# ───────────────────────── Каталог ─────────────────────────

class CategoryList(generics.ListAPIView):
    """GET /api/categories/ — дерево категорій."""
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related("children")


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/products/            — список (пагінація, фільтри, пошук, сортування)
    GET /api/products/{slug}/     — повна картка товару
    GET|POST /api/products/{slug}/reviews/ — відгуки
    """
    lookup_field = "slug"
    throttle_scope = None  # потрібен для @action(throttle_scope=...) нижче

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer

    def get_queryset(self):
        qs = (Product.objects.filter(is_active=True)
              .select_related("category")
              .prefetch_related("variants", "photos")
              .annotate(
                  rating_avg=Avg("reviews__rating", filter=Q(reviews__is_published=True)),
                  reviews_total=Count("reviews", filter=Q(reviews__is_published=True))))
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("category"):
            cat = Category.objects.filter(slug=p["category"]).first()
            qs = qs.filter(category_id__in=cat.with_children_ids()) if cat else qs.none()
        if p.get("q", "").strip():
            qs = search_products(qs, p["q"].strip())
        if p.get("sale") == "1":
            qs = qs.filter(old_price__gt=F("price"))
        if p.get("hit") == "1":
            qs = qs.filter(is_hit=True)
        try:
            if p.get("price_min"):
                qs = qs.filter(price__gte=Decimal(p["price_min"]))
            if p.get("price_max"):
                qs = qs.filter(price__lte=Decimal(p["price_max"]))
        except ArithmeticError:  # нечислове значення ігноруємо
            pass
        return qs.order_by({"price": "price", "-price": "-price"}.get(p.get("ordering"), "-created"), "pk")

    @action(detail=True, methods=["get", "post"], url_path="reviews", throttle_scope="reviews",
            throttle_classes=[ScopedRateThrottle])
    def reviews(self, request, slug=None):
        product = self.get_object()
        if request.method == "POST":
            ser = ReviewSerializer(data=request.data, context={"request": request})
            ser.is_valid(raise_exception=True)
            if ser.validated_data.pop("website", ""):  # бот заповнив приманку: вдаємо успіх, нічого не зберігаємо
                return Response(status=status.HTTP_201_CREATED)
            review = ser.save(product=product)
            return Response(ReviewSerializer(review, context={"request": request}).data, status=status.HTTP_201_CREATED)
        qs = product.reviews.filter(is_published=True).prefetch_related(
            Prefetch("photos", queryset=ReviewPhoto.objects.filter(is_approved=True), to_attr="approved_photos"))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(ReviewSerializer(page, many=True, context={"request": request}).data)


# ───────────────────────── Кошик (зберігається в сесії) ─────────────────────────

def cart_payload(request, **extra):
    cart = Cart(request)
    items = list(cart.items())  # спершу items(): він прибирає неактивні товари
    total = sum((i["subtotal"] for i in items), Decimal("0"))
    return {"count": len(cart), "total": f"{total:.2f}",
            "items": CartItemSerializer(items, many=True, context={"request": request}).data, **extra}


class CartView(APIView):
    """GET /api/cart/ — вміст кошика; DELETE — очистити."""

    def get(self, request):
        return Response(cart_payload(request))

    def delete(self, request):
        Cart(request).clear()
        return Response(cart_payload(request))


class CartItems(APIView):
    """POST /api/cart/items/ {"product": 1, "variant": 5, "quantity": 2} — додати товар."""

    def post(self, request):
        ser = CartAddSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        in_cart = Cart(request).add(d["product_obj"], d["quantity"], d["variant_obj"])
        extra = {}
        if d["variant_obj"] and in_cart >= d["variant_obj"].stock:
            extra["warning"] = f"У кошику {in_cart} шт. — це весь залишок."
        return Response(cart_payload(request, **extra), status=status.HTTP_201_CREATED)


class CartItem(APIView):
    """PATCH /api/cart/items/{key}/ {"quantity": 3} — змінити кількість (0 видаляє); DELETE — видалити."""

    def _check(self, request, key):
        if key not in Cart(request).data:
            raise NotFound("Такої позиції немає в кошику.")

    def patch(self, request, key):
        self._check(request, key)
        ser = CartUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        Cart(request).set(key, ser.validated_data["quantity"])
        return Response(cart_payload(request))

    def delete(self, request, key):
        self._check(request, key)
        Cart(request).remove(key)
        return Response(cart_payload(request))


# ───────────────────────── Замовлення ─────────────────────────

class Checkout(APIView):
    """POST /api/checkout/ — оформити замовлення з кошика (доступно й гостям)."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "checkout"

    def post(self, request):
        cart = Cart(request)
        items = list(cart.items())
        if not items:
            return Response({"detail": "Кошик порожній."}, status=status.HTTP_400_BAD_REQUEST)
        if any(i["limited"] for i in items):
            # Cart.items() уже зменшив кількість до залишку; не оформлюємо мовчки меншу кількість
            return Response({"detail": "Залишок змінився, кількість у кошику зменшено. Перегляньте кошик."},
                            status=status.HTTP_409_CONFLICT)
        ser = CheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            order = place_order(Order(**ser.validated_data), items, request.user)
        except OutOfStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        if request.user.is_authenticated:
            remember_delivery(request.user, order)
        cart.clear()
        request.session["last_order"] = order.pk
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/orders/ і /api/orders/{id}/ — лише замовлення поточного користувача."""
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")


# ───────────────────────── Токени ─────────────────────────

class TokenView(ObtainAuthToken):
    """POST /api/auth/token/ {"username": "email або логін", "password": "..."} -> {"token": "..."}."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        ser = self.serializer_class(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        token, _ = Token.objects.get_or_create(user=ser.validated_data["user"])
        return Response({"token": token.key})


class TokenLogout(APIView):
    """POST /api/auth/logout/ — видаляє токен, яким зроблено запит."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if isinstance(request.auth, Token):
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)