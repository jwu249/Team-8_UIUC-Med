from django.db import models
from django.urls import reverse

class MedService(models.Model):
    """
    Health clinic / hospital / urgent-care record.
    """
    # Original fields
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    email = models.EmailField(max_length=200, blank=True, null=True)
    number = models.CharField(max_length=200, blank=True, null=True)
    appointments_required = models.BooleanField(default=True)

    # New fields for demo / AI context
    description = models.TextField(blank=True, null=True,
        help_text="General summary of the facility (size, focus area, etc.)")
    services_offered = models.TextField(blank=True, null=True,
        help_text="Comma-separated list: e.g. 'Emergency, Radiology, Pediatrics'")
    accepts_insurance = models.BooleanField(default=True)
    payment_options = models.CharField(max_length=300, blank=True, null=True,
        help_text="e.g. 'Insurance, Cash, Payment Plan'")
    website = models.URLField(blank=True, null=True)
    google_rating = models.DecimalField(max_digits=2, decimal_places=1,
        blank=True, null=True, help_text="Rating out of 5, e.g. 4.2")
    hours = models.CharField(max_length=300, blank=True, null=True,
        help_text="e.g. 'Mon-Fri 8am-6pm, Sat 9am-2pm, Sun Closed'")

    # Geo coordinates — required for map display
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["name", "location"], name="unique_name_location")]

    def __str__(self):
        return f"{self.name} ({self.location})"

    def get_absolute_url(self):
        return reverse("service-detail", kwargs={"pk": self.pk})


class User(models.Model):
    """
    App-level user record. Stores geo data refreshed on each login / page load.
    """
    username = models.CharField(max_length=200, unique=True)
    email = models.EmailField(max_length=200, unique=True)
    password = models.CharField(max_length=200)
    access_token = models.CharField(max_length=200, unique=True)

    # Geo data — refreshed when user logs in or triggers location update
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.username}"


class History(models.Model):
    """
    Chat session record. Severity can escalate as the conversation reveals more symptoms.
    """
    SEVERITY_CHOICES = [
        ("non_emergency", "Non Emergency"),
        ("moderate",      "Moderate Severity"),
        ("urgent",        "Urgent Care Needed"),
    ]

    user = models.ForeignKey(User, related_name="history", on_delete=models.CASCADE)
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    # AI-assigned severity — can change as chat progresses
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES,
        blank=True, null=True,
        help_text="Severity categorization assigned by AI during chat"
    )
    # Service the user selected at the end of this chat session
    selected_service = models.ForeignKey(
        MedService, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="history_selections",
        help_text="Medical service the user chose at the end of this session"
    )

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user.username} @ {self.date}"
