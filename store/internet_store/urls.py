from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import TemplateView

from . import account_views as acc
from . import chat_views as chat
from . import favorite_views as fav
from . import novaposhta_views
from . import search_views
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/<slug:slug>/", views.catalog, name="catalog_category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),

    path("cart/", views.cart_detail, name="cart"),
    path("cart/drawer/", views.cart_drawer, name="cart_drawer"),
    path("cart/add/<int:pk>/", views.cart_add, name="cart_add"),
    path("cart/update/<str:key>/", views.cart_update, name="cart_update"),
    path("cart/remove/<str:key>/", views.cart_remove, name="cart_remove"),
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

    path("np/cities/", novaposhta_views.np_cities, name="np_cities"),
    path("np/warehouses/", novaposhta_views.np_warehouses, name="np_warehouses"),
    path("search/suggest/", search_views.search_suggest, name="search_suggest"),
    path("recent/clear/", views.recent_clear, name="recent_clear"),
    path("favorites/", fav.favorites_page, name="favorites"),
    path("favorites/toggle/<int:pk>/", fav.favorite_toggle, name="favorite_toggle"),
    path("chat/messages/", chat.customer_messages, name="chat_messages"),
    path("chat/send/", chat.customer_send, name="chat_send"),
    path("seller/chat/", chat.seller_inbox, name="seller_chat"),
    path("seller/chat/<int:pk>/", chat.seller_thread, name="seller_chat_thread"),
    path("seller/chat/<int:pk>/messages/", chat.seller_messages, name="seller_chat_messages"),
    path("seller/chat/<int:pk>/send/", chat.seller_send, name="seller_chat_send"),

    path("about/", TemplateView.as_view(template_name="pages/about.html"), name="about"),
    path("delivery/", TemplateView.as_view(template_name="pages/delivery.html"), name="delivery"),
    path("returns/", TemplateView.as_view(template_name="pages/returns.html"), name="returns"),
    path("contacts/", TemplateView.as_view(template_name="pages/contacts.html"), name="contacts"),
]
