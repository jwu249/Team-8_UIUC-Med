from django.contrib import admin
from .models import MedService, User, History # import models from models.py

# register all models into the admin server
admin.site.register(MedService)
admin.site.register(User)
admin.site.register(History)
