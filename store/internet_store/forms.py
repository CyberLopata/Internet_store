from django import forms

from .models import MAX_REVIEW_PHOTOS, Order, Review, validate_image_size


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["name", "phone", "email", "city", "address", "comment"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ім'я та прізвище", "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"placeholder": "+380...", "autocomplete": "tel", "inputmode": "tel"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email (необов'язково)", "autocomplete": "email"}),
            "city": forms.TextInput(attrs={"placeholder": "Місто"}),
            "address": forms.TextInput(attrs={"placeholder": "Відділення Нової пошти або адреса"}),
            "comment": forms.Textarea(attrs={"placeholder": "Коментар до замовлення", "rows": 3}),
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Кілька зображень в одному полі (<input type="file" multiple>); кожен файл перевіряється як картинка."""
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        files = [f for f in files if f]
        if len(files) > MAX_REVIEW_PHOTOS:
            raise forms.ValidationError(f"Можна додати не більше {MAX_REVIEW_PHOTOS} фото.")
        out = []
        for f in files:
            validate_image_size(f)
            out.append(super().clean(f, initial))
        return out


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Оцінка", choices=Review.RATING_CHOICES, coerce=int, widget=forms.RadioSelect,
        error_messages={"required": "Поставте оцінку від 1 до 5."},
    )
    # Приманка для ботів: людина це поле не бачить і не заповнює.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))
    photos = MultipleImageField(
        label="Фото", required=False,
        widget=MultipleFileInput(attrs={"accept": "image/*", "multiple": True}),
        error_messages={"invalid_image": "Один із файлів не є зображенням."},
    )

    class Meta:
        model = Review
        fields = ["name", "rating", "text"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ваше ім'я", "autocomplete": "name"}),
            "text": forms.Textarea(attrs={"placeholder": "Розкажіть, як вам товар", "rows": 4}),
        }

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 3:
            raise forms.ValidationError("Напишіть хоча б кілька слів.")
        return text
