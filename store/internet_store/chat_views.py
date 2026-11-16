import logging
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import ChatMessage, ChatThread, Product

log = logging.getLogger(__name__)
MAX_LEN = 1000
RATE_LIMIT = 10  # повідомлень покупця за хвилину


def _serialize(m):
    t = timezone.localtime(m.created)
    now = timezone.localtime()
    product = None
    if m.product_id and m.product.is_active:
        product = {"name": m.product.name, "url": m.product.get_absolute_url()}
    return {
        "id": m.pk, "seller": m.seller, "text": m.text, "product": product,
        "time": t.strftime("%H:%M" if t.date() == now.date() else "%d.%m %H:%M"),
    }


def _after(request):
    try:
        return max(int(request.GET.get("after", 0)), 0)
    except ValueError:
        return 0


def _clean_text(request):
    return (request.POST.get("text") or "").strip()[:MAX_LEN]


# ---------------- покупець ----------------

def _customer_thread(request, create=False):
    """Розмова поточного відвідувача (акаунт або гостьова сесія)."""
    sess, user = request.session, request.user
    guest_pk = sess.get("chat_thread")
    if user.is_authenticated:
        thread = ChatThread.objects.filter(user=user).first()
        if thread is None and guest_pk:  # гостьова розмова переходить до акаунта після входу
            thread = ChatThread.objects.filter(pk=guest_pk, user__isnull=True).first()
            if thread:
                thread.user = user
                thread.save(update_fields=["user"])
        if thread is None and create:
            thread = ChatThread.objects.create(user=user)
        return thread
    thread = ChatThread.objects.filter(pk=guest_pk, user__isnull=True).first() if guest_pk else None
    if thread is None and create:
        thread = ChatThread.objects.create()
        sess["chat_thread"] = thread.pk
    return thread


@require_GET
def customer_messages(request):
    thread = _customer_thread(request)
    if thread is None:
        return JsonResponse({"messages": [], "unread": 0})
    if request.GET.get("open"):
        thread.messages.filter(seller=True, read=False).update(read=True)
    msgs = thread.messages.filter(pk__gt=_after(request)).select_related("product")
    unread = thread.messages.filter(seller=True, read=False).count()
    return JsonResponse({"messages": [_serialize(m) for m in msgs], "unread": unread})


@require_POST
def customer_send(request):
    text = _clean_text(request)
    if not text:
        return JsonResponse({"error": "Напишіть повідомлення."}, status=400)
    thread = _customer_thread(request, create=True)
    since = timezone.now() - timedelta(minutes=1)
    if thread.messages.filter(seller=False, created__gte=since).count() >= RATE_LIMIT:
        return JsonResponse({"error": "Забагато повідомлень. Зачекайте хвилинку."}, status=429)
    product = None
    pid = request.POST.get("product")
    if pid and pid.isdigit():
        product = Product.objects.filter(pk=int(pid), is_active=True).first()
    had_unread = thread.messages.filter(seller=False, read=False).exists()
    msg = ChatMessage.objects.create(thread=thread, text=text, product=product)
    thread.save(update_fields=["updated"])
    if not had_unread:
        _notify_seller(request, thread, msg)
    return JsonResponse({"message": _serialize(msg)})


def _notify_seller(request, thread, msg):
    """Лист продавцю про нове звернення (лише якщо задано SELLER_NOTIFY_EMAIL)."""
    to = getattr(settings, "SELLER_NOTIFY_EMAIL", "")
    if not to:
        return
    link = request.build_absolute_uri(reverse("seller_chat_thread", args=[thread.pk]))
    try:
        send_mail(f"Нове повідомлення в чаті від {thread.customer_name}",
                  f"{msg.text}\n\nВідповісти: {link}", None, [to], fail_silently=True)
    except Exception:  # лист не повинен ламати чат
        log.exception("chat notify failed")


# ---------------- продавець (staff) ----------------

def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


@staff_required
def seller_inbox(request):
    threads = ChatThread.objects.select_related("user").annotate(
        unread=Count("messages", filter=Q(messages__seller=False, messages__read=False)),
        total=Count("messages"),
    ).filter(total__gt=0)
    items = []
    for t in threads:
        last = t.messages.order_by("-id").first()
        items.append({"thread": t, "unread": t.unread, "last": last})
    return render(request, "seller/inbox.html", {"items": items})


@staff_required
def seller_thread(request, pk):
    thread = get_object_or_404(ChatThread.objects.select_related("user"), pk=pk)
    return render(request, "seller/thread.html", {
        "thread": thread, "orders": thread.user.orders.all()[:5] if thread.user_id else [],
    })


@staff_required
@require_GET
def seller_messages(request, pk):
    thread = get_object_or_404(ChatThread, pk=pk)
    thread.messages.filter(seller=False, read=False).update(read=True)
    msgs = thread.messages.filter(pk__gt=_after(request)).select_related("product")
    return JsonResponse({"messages": [_serialize(m) for m in msgs], "unread": 0})


@staff_required
@require_POST
def seller_send(request, pk):
    thread = get_object_or_404(ChatThread, pk=pk)
    text = _clean_text(request)
    if not text:
        return JsonResponse({"error": "Напишіть повідомлення."}, status=400)
    msg = ChatMessage.objects.create(thread=thread, seller=True, text=text)
    thread.save(update_fields=["updated"])
    return JsonResponse({"message": _serialize(msg)})
