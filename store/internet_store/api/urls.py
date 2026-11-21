from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

app_name = "api"

router = SimpleRouter()
router.register("products", views.ProductViewSet, basename="product")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("", views.ApiRoot.as_view(), name="root"),
    path("categories/", views.CategoryList.as_view(), name="category-list"),
    path("cart/", views.CartView.as_view(), name="cart"),
    path("cart/items/", views.CartItems.as_view(), name="cart-items"),
    path("cart/items/<str:key>/", views.CartItem.as_view(), name="cart-item"),
    path("checkout/", views.Checkout.as_view(), name="checkout"),
    path("auth/token/", views.TokenView.as_view(), name="token"),
    path("auth/logout/", views.TokenLogout.as_view(), name="token-logout"),
    *router.urls,
]