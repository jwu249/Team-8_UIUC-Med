from django.contrib import admin
from .models import MedService, User, History


@admin.register(MedService)
class MedServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "google_rating", "hours", "accepts_insurance", "appointments_required", "latitude", "longitude")
    search_fields = ("name", "location", "services_offered")
    list_filter = ("accepts_insurance", "appointments_required")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "latitude", "longitude")
    search_fields = ("username", "email")


@admin.register(History)
class HistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "severity", "selected_service", "date")
    list_filter = ("severity",)
    search_fields = ("user__username", "message")
