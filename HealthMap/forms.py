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