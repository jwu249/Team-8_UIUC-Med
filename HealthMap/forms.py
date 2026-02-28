from django import forms
from .models import MedService

class MedServiceForm(forms.ModelForm):
    class Meta:
        model = MedService
        fields = [
            "name",
            "location",
            "email",
            "number",
            "appointments_required"
        ]

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]