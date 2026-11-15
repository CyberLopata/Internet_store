from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Order, Product, ProductImage, Review


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
