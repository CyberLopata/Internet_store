from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import TemplateView

from . import account_views as acc
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<slug:slug>/", views.catalog, name="catalog_category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),

    path("cart/", views.cart_detail, name="cart"),
    path("cart/drawer/", views.cart_drawer, name="cart_drawer"),
    path("cart/add/<int:pk>/", views.cart_add, name="cart_add"),
    path("cart/update/<int:pk>/", views.cart_update, name="cart_update"),
    path("cart/remove/<int:pk>/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/<int:pk>/success/", views.order_success, name="order_success"),

    path("account/", acc.account, name="account"),
    path("account/register/", acc.register, name="register"),
    path("account/login/", acc.login_view, name="login"),
    path("account/logout/", LogoutView.as_view(), name="logout"),
    path("account/orders/", acc.orders, name="account_orders"),
    path("account/orders/<int:pk>/", acc.order_detail, name="account_order"),
    path("account/password/", acc.PasswordChange.as_view(), name="password_change"),
    path("account/password-reset/", acc.PasswordReset.as_view(), name="password_reset"),
    path("account/password-reset/sent/", acc.PasswordResetDone.as_view(), name="password_reset_done"),
    path("account/reset/done/", acc.PasswordResetComplete.as_view(), name="password_reset_complete"),
    path("account/reset/<uidb64>/<token>/", acc.PasswordResetConfirm.as_view(), name="password_reset_confirm"),

    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("delivery/", TemplateView.as_view(template_name="pages/delivery.html"), name="delivery"),
    path("returns/", TemplateView.as_view(template_name="pages/returns.html"), name="returns"),
    path("contacts/", TemplateView.as_view(template_name="pages/contacts.html"), name="contacts"),
]
