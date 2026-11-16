from .cart import Cart
from .models import Category, ChatMessage


def shop(request):
    cart = Cart(request)
    user = request.user
    chat_unread = 0
    if user.is_authenticated and user.is_staff:
        chat_unread = ChatMessage.objects.filter(seller=False, read=False).count()
    return {
        "chat_unread": chat_unread,
        "menu_categories": Category.objects.filter(parent__isnull=True, in_menu=True),
        "cart_count": len(cart),
        "SHOP": {
            "name": "SHOP",
            "phone": "0 800 000 000",
            "email": "info@shop.example",
            "address": "м. Київ, вул. Прикладна, 1",
            "free_delivery_from": 1500,
        },
    }
