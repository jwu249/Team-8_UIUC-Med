from django.urls import path
from .views import hospital_list

urlpatterns = [
    path("hospitals/manual/", hospital_list, name="hospital-list-manual"),
]
