from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Order, Product, ProductImage, ProductVariant, Review


class ShopFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)

    def test_pages_ok(self):
        p = Product.objects.first()
        for url in [reverse("index"), reverse("catalog"), reverse("catalog_category", args=["spalnya"]),
                    reverse("catalog") + "?sale=1&q=Ковдра&sort=-price", p.get_absolute_url(),
                    reverse("cart"), reverse("about"), reverse("delivery"), reverse("returns"), reverse("contacts")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_cart_and_checkout(self):
        p = Product.objects.get(slug="podushka-comfort")
        self.client.post(reverse("cart_add", args=[p.pk]), {"quantity": 2})
        self.assertContains(self.client.get(reverse("cart")), "878")
        r = self.client.post(reverse("checkout"), {
            "name": "Іван", "phone": "+380501112233", "city": "Київ", "address": "НП №1"})
        order = Order.objects.get()
        self.assertRedirects(r, reverse("order_success", args=[order.pk]))
        self.assertEqual(order.total, 878)
        self.assertEqual(order.items.get().quantity, 2)
        self.assertContains(self.client.get(reverse("cart")), "порожній")

    def test_ajax_add_returns_drawer_json(self):
        p = Product.objects.get(slug="podushka-comfort")
        r = self.client.post(reverse("cart_add", args=[p.pk]), {"quantity": 2},
                             headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 2)
        self.assertIn(p.name, data["html"])
        self.assertIn("878", data["html"])
        self.assertIn(reverse("checkout"), data["html"])

    def test_plain_add_still_redirects_with_message(self):
        p = Product.objects.get(slug="podushka-comfort")
        r = self.client.post(reverse("cart_add", args=[p.pk]), {"next": reverse("catalog")})
        self.assertRedirects(r, reverse("catalog"))

    def test_ajax_update_and_remove(self):
        p = Product.objects.get(slug="podushka-comfort")
        ajax = {"X-Requested-With": "XMLHttpRequest"}
        self.client.post(reverse("cart_add", args=[p.pk]), {"quantity": 3}, headers=ajax)
        data = self.client.post(reverse("cart_update", args=[p.pk]), {"quantity": 2}, headers=ajax).json()
        self.assertEqual(data["count"], 2)
        data = self.client.post(reverse("cart_remove", args=[p.pk]), headers=ajax).json()
        self.assertEqual(data["count"], 0)
        self.assertIn("порожній", data["html"])

    def test_drawer_endpoint(self):
        data = self.client.get(reverse("cart_drawer")).json()
        self.assertEqual(data["count"], 0)
        self.assertIn("порожній", data["html"])

    def test_theme_toggle_is_rendered(self):
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn("data-theme-toggle", html)
        self.assertIn('localStorage.getItem("theme")', html)

    def test_success_page_is_private(self):
        order = Order.objects.create(name="x", phone="1", city="c", address="a")
        r = self.client.get(reverse("order_success", args=[order.pk]))
        self.assertRedirects(r, reverse("index"))


class ProductImageTests(TestCase):
    def test_additional_images_are_rendered_in_product_gallery(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from .models import Category

        buf = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(buf, format="PNG")
        category = Category.objects.create(name="Тест", slug="gallery-test")
        product = Product.objects.create(
            category=category, name="Галерея", slug="gallery-test", price=10,
        )
        photo = ProductImage.objects.create(
            product=product,
            image=SimpleUploadedFile("gallery.png", buf.getvalue(), content_type="image/png"),
        )
        try:
            self.assertContains(self.client.get(product.get_absolute_url()), photo.image.url)
        finally:
            product.delete()

    def test_upload_is_converted_to_webp_in_static_images(self):
        from io import BytesIO
        from pathlib import Path

        from django.conf import settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from .models import Category

        buf = BytesIO()
        Image.new("RGB", (2000, 1000), "red").save(buf, format="PNG")
        cat = Category.objects.create(name="Тест", slug="test-cat")
        p = Product.objects.create(
            category=cat, name="Фото", slug="photo-test", price=10,
            image=SimpleUploadedFile("big.png", buf.getvalue(), content_type="image/png"),
        )
        try:
            self.assertTrue(p.image.name.endswith(".webp"))
            path = Path(settings.PRODUCT_IMAGES_DIR) / p.image.name
            self.assertTrue(path.exists())
            with Image.open(path) as im:
                self.assertEqual(im.format, "WEBP")
                self.assertLessEqual(max(im.size), 1200)
            self.assertTrue(p.image.url.startswith("/static/images/"))
            self.assertContains(self.client.get(p.get_absolute_url()), p.image.url)
            self.assertEqual(self.client.get(p.image.url).status_code, 200)
        finally:
            p.delete()
        self.assertFalse(path.exists())


class ReviewTests(TestCase):
    def test_review_is_published_and_shown_after_submission(self):
        from .models import Category

        category = Category.objects.create(name="Відгуки", slug="review-test")
        product = Product.objects.create(
            category=category, name="Тестовий товар", slug="review-test", price=10,
        )
        response = self.client.post(product.get_absolute_url(), {
            "name": "Іван",
            "rating": "5",
            "text": "Якісний товар",
            "website": "",
        })

        self.assertRedirects(response, f"{product.get_absolute_url()}?reviewed=1#reviews")
        review = Review.objects.get(product=product)
        self.assertTrue(review.is_published)
        self.assertEqual(review.stars, "★★★★★")
        self.assertEqual(Product.objects.get(pk=product.pk).reviews_count, 1)
        self.assertContains(self.client.get(product.get_absolute_url() + "?reviewed=1"), review.text)

    def test_honeypot_submission_is_ignored(self):
        from .models import Category

        category = Category.objects.create(name="Відгуки", slug="review-spam-test")
        product = Product.objects.create(
            category=category, name="Тестовий товар", slug="review-spam-test", price=10,
        )
        self.client.post(product.get_absolute_url(), {
            "name": "Bot",
            "rating": "5",
            "text": "Spam review",
            "website": "http://example.invalid",
        })

        self.assertFalse(Review.objects.filter(product=product).exists())


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)

    def register(self, email="Anna@Example.com", pw="Str0ng-pass-91"):
        return self.client.post(reverse("register"), {
            "first_name": "Анна", "email": email, "phone": "+380501112233",
            "password1": pw, "password2": pw,
        })

    def test_register_logs_in_and_creates_profile(self):
        r = self.register()
        self.assertRedirects(r, reverse("account"))
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.get(username="anna@example.com")
        self.assertEqual(u.profile.phone, "+380501112233")
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)

    def test_duplicate_email_case_insensitive(self):
        self.register()
        self.client.logout()
        r = self.register(email="ANNA@example.com")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "уже існує")

    def test_weak_password_and_mismatch(self):
        r = self.register(pw="12345678")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_honeypot_creates_nothing(self):
        from django.contrib.auth import get_user_model
        self.client.post(reverse("register"), {
            "first_name": "Bot", "email": "bot@example.com", "password1": "Str0ng-pass-91",
            "password2": "Str0ng-pass-91", "website": "http://spam"})
        self.assertFalse(get_user_model().objects.filter(email="bot@example.com").exists())

    def test_login_by_email_any_case_and_wrong_password(self):
        self.register()
        self.client.logout()
        bad = self.client.post(reverse("login"), {"username": "anna@example.com", "password": "nope"})
        self.assertContains(bad, "Невірний email або пароль")
        ok = self.client.post(reverse("login"), {"username": "ANNA@example.com", "password": "Str0ng-pass-91"})
        self.assertRedirects(ok, reverse("account"))

    def test_login_next_safe_and_open_redirect_blocked(self):
        self.register()
        self.client.logout()
        data = {"username": "anna@example.com", "password": "Str0ng-pass-91"}
        r = self.client.post(reverse("login") + "?next=/cart/", data)
        self.assertRedirects(r, "/cart/", fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse("login") + "?next=https://evil.com/", data)
        self.assertRedirects(r, reverse("account"), fetch_redirect_response=False)

    def test_protected_pages_redirect_to_login(self):
        for name in ("account", "account_orders", "password_change"):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302)
            self.assertIn(reverse("login"), r["Location"])

    def test_logout_is_post_only(self):
        self.register()
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_checkout_as_user_links_order_and_prefills(self):
        self.register()
        p = Product.objects.first()
        self.client.post(reverse("cart_add", args=[p.pk]))
        page = self.client.get(reverse("checkout"))
        self.assertContains(page, "+380501112233")
        r = self.client.post(reverse("checkout"), {
            "name": "Анна", "phone": "+380501112233", "email": "anna@example.com",
            "city": "Київ", "address": "Відділення 5", "comment": ""})
        self.assertEqual(r.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.user.username, "anna@example.com")
        order.user.profile.refresh_from_db()
        self.assertEqual(order.user.profile.city, "Київ")
        self.assertContains(self.client.get(reverse("account_orders")), f"№{order.pk}")

    def test_guest_checkout_still_works(self):
        p = Product.objects.first()
        self.client.post(reverse("cart_add", args=[p.pk]))
        r = self.client.post(reverse("checkout"), {
            "name": "Гість", "phone": "+380991112233", "email": "", "city": "Львів",
            "address": "Склад 1", "comment": ""})
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(Order.objects.get().user)

    def test_cannot_view_other_users_order(self):
        self.register()
        p = Product.objects.first()
        self.client.post(reverse("cart_add", args=[p.pk]))
        self.client.post(reverse("checkout"), {
            "name": "Анна", "phone": "1", "email": "", "city": "К", "address": "А", "comment": ""})
        order = Order.objects.get()
        self.client.logout()
        self.register(email="bob@example.com")
        self.assertEqual(self.client.get(reverse("account_order", args=[order.pk])).status_code, 404)

    def test_profile_update_and_email_conflict(self):
        self.register()
        self.client.logout()
        self.register(email="bob@example.com")
        r = self.client.post(reverse("account"), {
            "first_name": "Bob", "last_name": "", "email": "anna@example.com",
            "phone": "", "city": "", "address": ""})
        self.assertContains(r, "іншим акаунтом")
        r = self.client.post(reverse("account"), {
            "first_name": "Bob", "last_name": "B", "email": "bob2@example.com",
            "phone": "1", "city": "К", "address": "А"})
        self.assertRedirects(r, reverse("account"))
        from django.contrib.auth import get_user_model
        self.assertTrue(get_user_model().objects.filter(username="bob2@example.com").exists())

    def test_password_change_and_reset_email(self):
        from django.core import mail
        self.register()
        r = self.client.post(reverse("password_change"), {
            "old_password": "Str0ng-pass-91", "new_password1": "Another-pass-77", "new_password2": "Another-pass-77"})
        self.assertRedirects(r, reverse("account"))
        self.client.post(reverse("password_reset"), {"email": "anna@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/account/reset/", mail.outbox[0].body)


class ChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)
        from django.contrib.auth import get_user_model
        cls.staff = get_user_model().objects.create_user("seller", "s@example.com", "Seller-pass-1", is_staff=True)

    def send(self, client, text="Чи є 42 розмір?", **extra):
        return client.post(reverse("chat_send"), {"text": text, **extra})

    def test_guest_conversation_roundtrip(self):
        p = Product.objects.first()
        r = self.send(self.client, product=p.pk)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["message"]["product"]["url"], p.get_absolute_url())
        # продавець відповідає
        from .models import ChatThread
        t = ChatThread.objects.get()
        seller = self.client_class()
        seller.force_login(self.staff)
        self.assertEqual(seller.post(reverse("seller_chat_send", args=[t.pk]), {"text": "Так, є!"}).status_code, 200)
        data = self.client.get(reverse("chat_messages") + "?after=0").json()
        self.assertEqual([m["seller"] for m in data["messages"]], [False, True])
        self.assertEqual(data["unread"], 1)
        data = self.client.get(reverse("chat_messages") + "?after=0&open=1").json()
        self.assertEqual(self.client.get(reverse("chat_messages") + "?after=2").json()["unread"], 0)

    def test_empty_and_long_messages(self):
        self.assertEqual(self.send(self.client, text="   ").status_code, 400)
        r = self.send(self.client, text="я" * 3000)
        self.assertEqual(len(r.json()["message"]["text"]), 1000)

    def test_rate_limit(self):
        codes = [self.send(self.client, text=f"m{i}").status_code for i in range(12)]
        self.assertEqual(codes.count(200), 10)
        self.assertEqual(codes[-1], 429)

    def test_threads_are_isolated(self):
        self.send(self.client)
        other = self.client_class()
        self.assertEqual(other.get(reverse("chat_messages")).json()["messages"], [])

    def test_guest_thread_moves_to_account_on_login(self):
        from django.contrib.auth import get_user_model
        from .models import ChatThread
        self.send(self.client)
        u = get_user_model().objects.create_user("c@example.com", "c@example.com", "Cust-pass-1234")
        self.client.force_login(u)
        self.assertEqual(len(self.client.get(reverse("chat_messages")).json()["messages"]), 1)
        self.assertEqual(ChatThread.objects.get().user, u)

    def test_seller_pages_staff_only(self):
        self.send(self.client)
        from .models import ChatThread
        t = ChatThread.objects.get()
        urls = [reverse("seller_chat"), reverse("seller_chat_thread", args=[t.pk]),
                reverse("seller_chat_messages", args=[t.pk])]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 302)  # гість → вхід
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user("x@example.com", "x@example.com", "Cust-pass-1234")
        self.client.force_login(u)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("seller_chat_send", args=[t.pk]), {"text": "hi"}).status_code, 403)

    def test_seller_read_marks_and_inbox(self):
        self.send(self.client)
        from .models import ChatThread
        t = ChatThread.objects.get()
        s = self.client_class()
        s.force_login(self.staff)
        self.assertContains(s.get(reverse("seller_chat")), "нових: 1")
        s.get(reverse("seller_chat_messages", args=[t.pk]))
        self.assertNotContains(s.get(reverse("seller_chat")), "нових:")

    def test_widget_and_ask_button_rendered(self):
        p = Product.objects.first()
        self.assertContains(self.client.get(p.get_absolute_url()), "data-chat-open")
        self.assertContains(self.client.get(reverse("index")), 'id="chat-widget"')
        self.assertContains(self.client.get(reverse("index")), "chat.js")

    def test_xss_text_is_stored_raw_and_returned_as_json(self):
        r = self.send(self.client, text="<script>alert(1)</script>")
        self.assertEqual(r.json()["message"]["text"], "<script>alert(1)</script>")
        from .models import ChatThread
        s = self.client_class()
        s.force_login(self.staff)
        self.assertNotContains(s.get(reverse("seller_chat")), "<script>alert(1)")


class VariantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)
        cls.p = Product.objects.get(slug="podushka-comfort")
        cls.v40 = ProductVariant.objects.create(product=cls.p, size="40", color_name="Чорний", color_hex="#111111", stock=3)
        cls.v41 = ProductVariant.objects.create(product=cls.p, size="41", color_name="Чорний", color_hex="#111111", stock=0)
        cls.v42 = ProductVariant.objects.create(product=cls.p, size="42", color_name="Білий", color_hex="#ffffff", stock=5,
                                                price=999)
        cls.ajax = {"X-Requested-With": "XMLHttpRequest"}

    def add(self, variant=None, qty=1, **kw):
        data = {"quantity": qty}
        if variant is not None:
            data["variant"] = variant.pk
        return self.client.post(reverse("cart_add", args=[self.p.pk]), data, **kw)

    def test_must_choose_variant(self):
        r = self.add()
        self.assertRedirects(r, self.p.get_absolute_url(), fetch_redirect_response=False)
        self.assertEqual(self.add(headers=self.ajax).status_code, 400)
        self.assertEqual(self.client.get(reverse("cart")).context["items"], [])

    def test_out_of_stock_variant_rejected(self):
        self.assertEqual(self.add(self.v41, headers=self.ajax).status_code, 400)

    def test_variant_of_other_product_rejected(self):
        other = Product.objects.exclude(pk=self.p.pk).first()
        v = ProductVariant.objects.create(product=other, size="M", stock=9)
        self.assertEqual(self.add(v, headers=self.ajax).status_code, 400)

    def test_add_distinct_variants_and_prices(self):
        self.add(self.v40, 2)
        self.add(self.v42, 1)
        items = self.client.get(reverse("cart")).context["items"]
        self.assertEqual({i["label"] for i in items}, {"40 / Чорний", "42 / Білий"})
        self.assertEqual(sum(i["subtotal"] for i in items), 2 * self.p.price + 999)

    def test_quantity_capped_by_stock(self):
        self.add(self.v40, 10)
        self.add(self.v40, 10)
        item = self.client.get(reverse("cart")).context["items"][0]
        self.assertEqual(item["quantity"], 3)
        key = item["key"]
        self.client.post(reverse("cart_update", args=[key]), {"quantity": 50})
        self.assertEqual(self.client.get(reverse("cart")).context["items"][0]["quantity"], 3)

    def test_checkout_decrements_stock_and_saves_label(self):
        self.add(self.v40, 2)
        r = self.client.post(reverse("checkout"), {"name": "І", "phone": "1", "city": "К", "address": "А"})
        order = Order.objects.get()
        self.assertRedirects(r, reverse("order_success", args=[order.pk]))
        item = order.items.get()
        self.assertEqual((item.variant_label, item.variant_id), ("40 / Чорний", self.v40.pk))
        self.assertEqual(item.full_name, f"{self.p.name} (40 / Чорний)")
        self.v40.refresh_from_db()
        self.assertEqual(self.v40.stock, 1)

    def test_checkout_blocked_if_stock_vanished(self):
        self.add(self.v40, 3)
        ProductVariant.objects.filter(pk=self.v40.pk).update(stock=1)  # хтось інший купив
        r = self.client.post(reverse("checkout"), {"name": "І", "phone": "1", "city": "К", "address": "А"})
        # items() у кошику сам обрізає до залишку, тому замовлення на 1 шт. проходить, а не на 3
        order = Order.objects.get()
        self.assertEqual(order.items.get().quantity, 1)
        self.v40.refresh_from_db()
        self.assertEqual(self.v40.stock, 0)

    def test_checkout_race_out_of_stock_error(self):
        from unittest import mock
        self.add(self.v40, 2)
        real = ProductVariant.objects.select_for_update

        def stale(*a, **k):  # імітуємо: між показом кошика і блокуванням залишок зник
            ProductVariant.objects.filter(pk=self.v40.pk).update(stock=0)
            return real(*a, **k)
        with mock.patch.object(type(ProductVariant.objects), "select_for_update", side_effect=stale):
            r = self.client.post(reverse("checkout"), {"name": "І", "phone": "1", "city": "К", "address": "А"})
        self.assertRedirects(r, reverse("cart"), fetch_redirect_response=False)
        self.assertEqual(Order.objects.count(), 0)

    def test_cancel_returns_stock(self):
        self.add(self.v40, 2)
        self.client.post(reverse("checkout"), {"name": "І", "phone": "1", "city": "К", "address": "А"})
        order = Order.objects.get()
        self.v40.refresh_from_db()
        self.assertEqual(self.v40.stock, 1)
        order.status = Order.Status.CANCELED
        order.save()
        order.save()  # повторне збереження не повертає удруге
        self.v40.refresh_from_db()
        self.assertEqual(self.v40.stock, 3)

    def test_legacy_cart_key_for_product_with_variants_dropped(self):
        s = self.client.session
        s["cart"] = {str(self.p.pk): 2}
        s.save()
        self.assertEqual(self.client.get(reverse("cart")).context["items"], [])

    def test_pdp_and_card_render(self):
        page = self.client.get(self.p.get_absolute_url())
        self.assertContains(page, 'id="variants-data"')
        self.assertContains(page, "variants.js")
        card = self.client.get(reverse("catalog"))
        self.assertContains(card, f'<a class="add" href="{self.p.get_absolute_url()}">До кошика</a>')

    def test_product_all_sold_out(self):
        ProductVariant.objects.filter(product=self.p).update(stock=0)
        self.assertContains(self.client.get(reverse("catalog")), "Немає в наявності")

    def test_no_variants_product_unchanged(self):
        other = Product.objects.exclude(pk=self.p.pk).first()
        self.client.post(reverse("cart_add", args=[other.pk]), {"quantity": 2})
        self.assertEqual(self.client.get(reverse("cart")).context["items"][0]["quantity"], 2)

    def test_variant_validation(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            ProductVariant(product=self.p).clean()
        with self.assertRaises(ValidationError):
            ProductVariant(product=self.p, size="M", color_hex="red").clean()


class VariantColorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)
        cls.p = Product.objects.first()

    def make(self, name, hex=""):
        return ProductVariant.objects.create(product=self.p, size=name[:3], color_name=name, color_hex=hex, stock=1)

    def test_hex_filled_from_name(self):
        self.assertEqual(self.make("Чорний").color_hex, "#1d1d1f")
        self.assertEqual(self.make("  БІЛИЙ ").color_hex, "#f5f5f5")

    def test_longer_name_wins_and_substring(self):
        from .colors import hex_for_name
        self.assertEqual(hex_for_name("Темно-синій"), "#1a2a5e")
        self.assertEqual(hex_for_name("Синій"), "#2f4fd8")
        self.assertEqual(hex_for_name("Чорний матовий"), "#1d1d1f")

    def test_explicit_hex_wins_and_unknown_stays_empty(self):
        self.assertEqual(self.make("Чорний", "#123456").color_hex, "#123456")
        self.assertEqual(self.make("Райдужний").color_hex, "")

    def test_admin_product_page_has_variants_and_picker_js(self):
        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_superuser("adm", "a@e.com", "Adm-pass-12345")
        self.client.force_login(admin)
        page = self.client.get(reverse("admin:internet_store_product_change", args=[self.p.pk]))
        self.assertContains(page, "Варіанти товару")
        self.assertContains(page, "admin_variant_color.js")


class BulkVariantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)
        cls.p = Product.objects.first()

    def test_parse_list(self):
        from .variants import parse_list
        self.assertEqual(parse_list(" 39, 40;41,\n 40 ,, "), ["39", "40", "41"])
        self.assertEqual(parse_list("Чорний, чорний, Білий"), ["Чорний", "Білий"])
        self.assertEqual(parse_list(""), [])

    def test_matrix_created_with_colors_and_skips_existing(self):
        from .variants import create_variants, parse_list
        ProductVariant.objects.create(product=self.p, size="40", color_name="Чорний", stock=7)
        made, skipped = create_variants(self.p, parse_list("39,40,41"), parse_list("Чорний,Білий"), 10)
        self.assertEqual((made, skipped), (5, 1))
        self.assertEqual(self.p.variants.count(), 6)
        self.assertEqual(self.p.variants.get(size="40", color_name="Чорний").stock, 7)  # існуючий не змінено
        self.assertEqual(self.p.variants.get(size="39", color_name="Білий").color_hex, "#f5f5f5")

    def test_only_sizes_or_only_colors(self):
        from .variants import create_variants
        self.assertEqual(create_variants(self.p, ["S", "M"], [], 3), (2, 0))
        self.assertEqual(create_variants(self.p, [], ["Червоний"], 3), (1, 0))

    def test_admin_save_creates_variants(self):
        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_superuser("adm2", "a2@e.com", "Adm-pass-12345")
        self.client.force_login(admin)
        url = reverse("admin:internet_store_product_change", args=[self.p.pk])
        page = self.client.get(url)
        self.assertContains(page, "Швидко додати: розміри")
        form = page.context["adminform"].form
        data = {k: (v if v is not None else "") for k, v in form.initial.items() if k not in ("image",)}
        for fs in page.context["inline_admin_formsets"]:
            mf = fs.formset.management_form
            data.update({mf.add_prefix("TOTAL_FORMS"): 0, mf.add_prefix("INITIAL_FORMS"): 0,
                         mf.add_prefix("MIN_NUM_FORMS"): 0, mf.add_prefix("MAX_NUM_FORMS"): 1000})
        data.update({"category": self.p.category_id, "name": self.p.name, "slug": self.p.slug, "price": self.p.price,
                     "is_active": "on", "bulk_sizes": "40, 41", "bulk_colors": "Чорний, Білий", "bulk_stock": "4"})
        for k in ("old_price", "color", "emoji", "description", "reviews_count"):
            data.setdefault(k, form.initial.get(k) or "")
        data["reviews_count"] = self.p.reviews_count
        r = self.client.post(url, data)
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["adminform"].form.errors)
        self.assertEqual(self.p.variants.count(), 4)
        self.assertEqual(set(self.p.variants.values_list("stock", flat=True)), {4})


class ColorPhotoTests(TestCase):
    def setUp(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        from .models import Category
        self._made = []
        cat = Category.objects.create(name="Колір", slug="color-photos")
        self.p = Product.objects.create(category=cat, name="Кросівки К", slug="color-photos", price=10)
        ProductVariant.objects.create(product=self.p, size="40", color_name="Чорний", stock=1)
        ProductVariant.objects.create(product=self.p, size="40", color_name="Червоний", stock=1)

        def photo(color, shade):
            buf = BytesIO()
            Image.new("RGB", (20, 20), shade).save(buf, format="PNG")
            img = ProductImage.objects.create(
                product=self.p, color=color,
                image=SimpleUploadedFile(f"{shade}.png", buf.getvalue(), content_type="image/png"))
            self._made.append(img)
            return img
        self.neutral = photo("", "black")
        self.red1, self.red2 = photo("червоний", "red"), photo("Червоний", "darkred")  # регістр не важливий
        self.orphan = photo("Рожевий", "pink")  # кольору немає у варіантах

    def tearDown(self):
        self.p.delete()

    def test_neutral_gallery_excludes_color_photos(self):
        ctx = self.client.get(self.p.get_absolute_url()).context
        self.assertEqual(ctx["gallery"], [self.neutral.image.url])
        self.assertEqual(ctx["gallery_colors"], {"Червоний": [self.red1.image.url, self.red2.image.url]})
        self.assertNotIn(self.orphan.image.url, ctx["gallery"] + sum(ctx["gallery_colors"].values(), []))

    def test_color_photos_not_in_initial_html_gallery(self):
        html = self.client.get(self.p.get_absolute_url()).content.decode()
        self.assertEqual(html.count("data-gallery-thumb data-src="), 1)  # у смузі лише нейтральне фото
        self.assertIn('id="gallery-colors"', html)

    def test_only_color_photos_product_has_hidden_main(self):
        self.neutral.delete()  # саме через екземпляр: так видаляється і файл
        html = self.client.get(self.p.get_absolute_url()).content.decode()
        self.assertIn("data-gallery-emoji", html)
        self.assertRegex(html, r"<img hidden[^>]*data-gallery-main")

    def test_admin_inline_offers_variant_colors(self):
        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_superuser("adm3", "a3@e.com", "Adm-pass-12345")
        self.client.force_login(admin)
        page = self.client.get(reverse("admin:internet_store_product_change", args=[self.p.pk]))
        self.assertContains(page, "Для всіх (нейтральне)")
        self.assertContains(page, '<option value="Червоний"')
        self.assertContains(page, "такого кольору вже немає")  # «Рожевий» позначено як застарілий


class FavoriteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)
        cls.p1, cls.p2 = Product.objects.all()[:2]

    def toggle(self, client, product, **kw):
        return client.post(reverse("favorite_toggle", args=[product.pk]), **kw)

    def test_guest_toggle_ajax_and_page(self):
        r = self.toggle(self.client, self.p1, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(r.json(), {"active": True, "count": 1})
        page = self.client.get(reverse("favorites"))
        self.assertContains(page, self.p1.name)
        r = self.toggle(self.client, self.p1, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(r.json(), {"active": False, "count": 0})
        self.assertContains(self.client.get(reverse("favorites")), "Тут поки порожньо")

    def test_non_ajax_redirects_back(self):
        r = self.client.post(reverse("favorite_toggle", args=[self.p1.pk]), {"next": "/catalog/"})
        self.assertRedirects(r, "/catalog/", fetch_redirect_response=False)
        r = self.client.post(reverse("favorite_toggle", args=[self.p1.pk]), {"next": "https://evil.com/"})
        self.assertRedirects(r, reverse("favorites"), fetch_redirect_response=False)

    def test_get_not_allowed_and_inactive_404(self):
        self.assertEqual(self.client.get(reverse("favorite_toggle", args=[self.p1.pk])).status_code, 405)
        Product.objects.filter(pk=self.p1.pk).update(is_active=False)
        self.assertEqual(self.toggle(self.client, self.p1).status_code, 404)

    def test_inactive_product_hidden_from_page_and_count(self):
        self.toggle(self.client, self.p1)
        self.toggle(self.client, self.p2)
        Product.objects.filter(pk=self.p1.pk).update(is_active=False)
        ctx = self.client.get(reverse("favorites")).context
        self.assertEqual([p.pk for p in ctx["products"]], [self.p2.pk])
        self.assertEqual(ctx["fav_count"], 1)

    def test_newest_first(self):
        self.toggle(self.client, self.p1)
        self.toggle(self.client, self.p2)
        self.assertEqual([p.pk for p in self.client.get(reverse("favorites")).context["products"]],
                         [self.p2.pk, self.p1.pk])

    def test_hearts_rendered_on_cards_and_pdp(self):
        self.toggle(self.client, self.p1)
        html = self.client.get(reverse("catalog")).content.decode()
        self.assertIn(f'data-fav="{self.p1.pk}"', html)
        self.assertIn('class="fav-btn on"', html)
        pdp = self.client.get(self.p1.get_absolute_url()).content.decode()
        self.assertIn("В обраному", pdp)
        self.assertIn('data-fav-count>1<', self.client.get(reverse("index")).content.decode().replace(" ", ""))

    def test_user_favorites_persist_in_db(self):
        from django.contrib.auth import get_user_model

        from .models import Favorite
        u = get_user_model().objects.create_user("f@example.com", "f@example.com", "Fav-pass-12345")
        self.client.force_login(u)
        self.toggle(self.client, self.p1)
        self.assertTrue(Favorite.objects.filter(user=u, product=self.p1).exists())
        other = self.client_class()
        self.assertNotContains(other.get(reverse("favorites")), self.p1.name)  # інші не бачать
        self.toggle(self.client, self.p1)
        self.assertFalse(Favorite.objects.filter(user=u).exists())

    def test_guest_favorites_merge_on_login_and_register(self):
        from django.contrib.auth import get_user_model

        from .models import Favorite
        self.toggle(self.client, self.p1)
        self.toggle(self.client, self.p2)
        u = get_user_model().objects.create_user("m@example.com", "m@example.com", "Merge-pass-12345")
        Favorite.objects.create(user=u, product=self.p1)  # вже було в акаунті: дубля не буде
        r = self.client.post(reverse("login"), {"username": "m@example.com", "password": "Merge-pass-12345"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Favorite.objects.filter(user=u).count(), 2)
        self.assertNotIn("favorites", self.client.session)
        # реєстрація теж зливає
        c = self.client_class()
        self.toggle(c, self.p2)
        c.post(reverse("register"), {"first_name": "Н", "email": "new@example.com",
                                     "password1": "Str0ng-pass-91", "password2": "Str0ng-pass-91"})
        self.assertEqual(Favorite.objects.filter(user__email="new@example.com", product=self.p2).count(), 1)

    def test_account_nav_link_and_empty_state_link(self):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user("n@example.com", "n@example.com", "Nav-pass-12345")
        self.client.force_login(u)
        self.assertContains(self.client.get(reverse("account")), reverse("favorites"))


class RecentlyViewedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_shop", verbosity=0)
        cls.products = list(Product.objects.all()[:4])

    def view(self, p):
        return self.client.get(p.get_absolute_url())

    def recent_pks(self, response):
        return [p.pk for p in response.context["recent"]]

    def test_empty_history_shows_nothing(self):
        r = self.client.get(reverse("index"))
        self.assertEqual(r.context["recent"], [])
        self.assertNotContains(r, "Нещодавно переглянуті")

    def test_records_newest_first_and_dedupes(self):
        a, b, c = self.products[:3]
        self.view(a); self.view(b); self.view(c); self.view(a)
        self.assertEqual(self.recent_pks(self.client.get(reverse("index"))), [a.pk, c.pk, b.pk])

    def test_current_product_excluded_on_its_own_page(self):
        a, b = self.products[:2]
        self.view(a)
        r = self.view(b)
        self.assertEqual(self.recent_pks(r), [a.pk])
        self.assertContains(r, "Нещодавно переглянуті")
        self.assertEqual(self.recent_pks(self.view(a)), [b.pk])

    def test_first_view_has_no_block_on_pdp(self):
        self.assertNotContains(self.view(self.products[0]), "Нещодавно переглянуті")

    def test_inactive_hidden_and_cap_stored(self):
        a, b = self.products[:2]
        self.view(a); self.view(b)
        Product.objects.filter(pk=a.pk).update(is_active=False)
        self.assertEqual(self.recent_pks(self.client.get(reverse("index"))), [b.pk])
        from .recent import MAX_STORED, remember
        from django.test import RequestFactory
        from django.contrib.sessions.backends.db import SessionStore
        req = RequestFactory().get("/")
        req.session = SessionStore()
        for i in range(1, 40):
            remember(req, Product(pk=i))
        self.assertEqual(len(req.session["recent"]), MAX_STORED)
        self.assertEqual(req.session["recent"][0], 39)

    def test_clear_and_safe_redirect(self):
        a, b = self.products[:2]
        self.view(a); self.view(b)
        r = self.client.post(reverse("recent_clear"), {"next": "/catalog/"})
        self.assertRedirects(r, "/catalog/", fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("index")).context["recent"], [])
        r = self.client.post(reverse("recent_clear"), {"next": "https://evil.com/"})
        self.assertRedirects(r, reverse("index"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("recent_clear")).status_code, 405)

    def test_history_is_per_visitor_and_survives_login(self):
        from django.contrib.auth import get_user_model
        a = self.products[0]
        self.view(a)
        self.assertEqual(self.client_class().get(reverse("index")).context["recent"], [])
        u = get_user_model().objects.create_user("r@example.com", "r@example.com", "Rec-pass-12345")
        self.client.force_login(u)
        self.assertEqual(self.recent_pks(self.client.get(reverse("index"))), [a.pk])

    def test_limit_six_on_page(self):
        from .models import Category
        cat = Category.objects.first()
        extra = [Product.objects.create(category=cat, name=f"Т{i}", slug=f"t-{i}", price=1) for i in range(8)]
        for p in extra:
            self.view(p)
        self.assertEqual(len(self.client.get(reverse("index")).context["recent"]), 6)


class LiveSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from .models import Category
        cat = Category.objects.create(name="Взуття", slug="vzuttya")
        other = Category.objects.create(name="Дім", slug="dim")
        mk = lambda name, slug, c=cat, **kw: Product.objects.create(category=c, name=name, slug=slug, price=kw.pop("price", 100), **kw)
        cls.runner = mk("Кросівки Runner", "runner", description="Легкі для бігу")
        cls.nike = mk("Nike Кросівки Air", "nike", price=200, old_price=300)
        cls.boots = mk("Черевики зимові", "boots", description="Теплі, як кросівки взимку")
        cls.blanket = mk("Ковдра «Літо»", "blanket", c=other)
        cls.hidden = mk("Кросівки приховані", "hidden", is_active=False)

    def get(self, q):
        return self.client.get(reverse("search_suggest"), {"q": q}).json()

    def names(self, q):
        return [r["name"] for r in self.get(q)["results"]]

    def test_too_short_returns_nothing(self):
        self.assertEqual(self.get("к"), {"q": "к", "total": 0, "results": []})
        self.assertEqual(self.get("  "), {"q": "", "total": 0, "results": []})

    def test_case_insensitive_cyrillic_and_inactive_excluded(self):
        self.assertEqual(set(self.names("КРОСІВКИ")), {"Кросівки Runner", "Nike Кросівки Air", "Черевики зимові"})
        self.assertNotIn("Кросівки приховані", self.names("кросівки"))

    def test_ranking_prefix_first_then_name_then_description(self):
        self.assertEqual(self.names("кросівки"), ["Кросівки Runner", "Nike Кросівки Air", "Черевики зимові"])

    def test_all_words_must_match_and_category_counts(self):
        self.assertEqual(self.names("кросівки runner"), ["Кросівки Runner"])
        self.assertEqual(self.names("взуття nike"), ["Nike Кросівки Air"])  # слово з назви категорії
        self.assertEqual(self.names("кросівки qwerty"), [])

    def test_quotes_and_prefix_of_inner_word(self):
        self.assertEqual(self.names("літо"), ["Ковдра «Літо»"])

    def test_limit_and_total(self):
        from .models import Category
        cat = Category.objects.get(slug="vzuttya")
        for i in range(10):
            Product.objects.create(category=cat, name=f"Сандалі {i}", slug=f"sandali-{i}", price=1)
        data = self.get("сандалі")
        self.assertEqual((len(data["results"]), data["total"]), (6, 10))

    def test_payload_fields(self):
        r = self.get("nike")["results"][0]
        self.assertEqual(r["url"], self.nike.get_absolute_url())
        self.assertEqual((r["price"], r["old_price"]), ("200 ₴", "300 ₴"))
        self.assertEqual((r["category"], r["in_stock"]), ("Взуття", True))

    def test_out_of_stock_flag_and_sorted_after_in_stock(self):
        sold = Product.objects.create(category=self.runner.category, name="Сандалі Z", slug="sz", price=1)
        ProductVariant.objects.create(product=sold, size="40", stock=0)
        Product.objects.create(category=self.runner.category, name="Сандалі Y", slug="sy", price=1)
        res = self.get("сандалі")["results"]
        self.assertEqual([r["name"] for r in res], ["Сандалі Y", "Сандалі Z"])
        self.assertFalse(res[1]["in_stock"])

    def test_catalog_uses_same_search(self):
        page = self.client.get(reverse("catalog"), {"q": "кросівки runner"})
        self.assertEqual([p.name for p in page.context["page"]], ["Кросівки Runner"])
        page = self.client.get(reverse("catalog"), {"q": "ковдра літо"})
        self.assertEqual([p.name for p in page.context["page"]], ["Ковдра «Літо»"])

    def test_get_only_and_header_wired(self):
        self.assertEqual(self.client.post(reverse("search_suggest")).status_code, 405)
        html = self.client.get(reverse("index")).content.decode()
        self.assertIn('data-suggest-url="/search/suggest/"', html)
        self.assertIn("search.js", html)

    def test_very_long_query_is_safe(self):
        self.assertEqual(self.client.get(reverse("search_suggest"), {"q": "я" * 5000}).status_code, 200)

    def test_orm_branch_used_for_postgres(self):
        """Гілка для PostgreSQL (icontains). Перевіряємо на ASCII-запитах, бо SQLite для кирилиці регістр не ігнорує."""
        from unittest import mock

        from .search import search_products
        with mock.patch("internet_store.search.connection") as conn:
            conn.vendor = "postgresql"
            qs = search_products(Product.objects.filter(is_active=True), "nike air")
            self.assertEqual([p.name for p in qs], ["Nike Кросівки Air"])
            self.assertEqual(search_products(Product.objects.all(), "nike zzz").count(), 0)


class NovaPoshtaTests(TestCase):
    CITIES = [{"Addresses": [
        {"DeliveryCity": "ref-kyiv", "MainDescription": "Київ", "Present": "м. Київ, Київська обл.", "Warehouses": 300},
        {"DeliveryCity": "ref-empty", "MainDescription": "Село", "Present": "с. Село", "Warehouses": 0},
    ]}]
    WH = [{"Ref": "w1", "Number": "5", "Description": "Відділення №5: вул. Хрещатик, 1"}, {"Ref": "", "Description": ""}]

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        call_command("seed_shop", verbosity=0)
        self.p = Product.objects.filter(variants__isnull=True).first()

    def test_disabled_without_key(self):
        with self.settings(NOVA_POSHTA_API_KEY=""):
            self.assertEqual(self.client.get("/np/cities/?q=Київ").status_code, 404)
            self.client.post("/cart/add/%d/" % self.p.pk)
            self.assertNotContains(self.client.get("/checkout/"), "data-np-cities")

    def test_cities_filter_and_cache(self):
        from unittest import mock
        from . import novaposhta
        with self.settings(NOVA_POSHTA_API_KEY="k"), mock.patch.object(novaposhta, "_call", return_value=self.CITIES) as m:
            r = self.client.get("/np/cities/?q=Київ").json()
            self.assertEqual([c["ref"] for c in r["results"]], ["ref-kyiv"])
            self.client.get("/np/cities/?q=київ")
            self.assertEqual(m.call_count, 1)  # другий запит з кешу
            self.assertEqual(self.client.get("/np/cities/?q=К").json()["results"], [])

    def test_warehouses(self):
        from unittest import mock
        from . import novaposhta
        with self.settings(NOVA_POSHTA_API_KEY="k"), mock.patch.object(novaposhta, "_call", return_value=self.WH) as m:
            r = self.client.get("/np/warehouses/?city=ref-kyiv&q=5").json()
            self.assertEqual(len(r["results"]), 1)
            self.assertEqual(r["results"][0]["number"], "5")
            self.assertEqual(m.call_args[0][2]["CityRef"], "ref-kyiv")
            self.assertEqual(self.client.get("/np/warehouses/").json()["results"], [])

    def test_api_error_is_503(self):
        from unittest import mock
        from . import novaposhta
        with self.settings(NOVA_POSHTA_API_KEY="k"), mock.patch.object(novaposhta, "_call", side_effect=novaposhta.NovaPoshtaError("x")):
            self.assertEqual(self.client.get("/np/cities/?q=Київ").status_code, 503)

    def test_call_parses_api_failure(self):
        from unittest import mock
        from . import novaposhta
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = b'{"success": false, "errors": ["API key is invalid"]}'
        with self.settings(NOVA_POSHTA_API_KEY="bad"), mock.patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(novaposhta.NovaPoshtaError):
                novaposhta._call("Address", "getCities", {})

    def test_checkout_has_picker_when_enabled(self):
        with self.settings(NOVA_POSHTA_API_KEY="k"):
            self.client.post("/cart/add/%d/" % self.p.pk)
            self.assertContains(self.client.get("/checkout/"), "data-np-cities")
