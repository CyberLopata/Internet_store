from django import forms

from .models import Order, Review


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


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Оцінка", choices=Review.RATING_CHOICES, coerce=int, widget=forms.RadioSelect,
        error_messages={"required": "Поставте оцінку від 1 до 5."},
    )
    # Приманка для ботів: людина це поле не бачить і не заповнює.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

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
