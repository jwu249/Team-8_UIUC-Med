from django.urls import path
from .views import hospital_list, hospital_list_render

urlpatterns = [
    path("hospitals/manual/", hospital_list, name="hospital-list-manual"),
    path("hospitals/render/", hospital_list_render, name="hospital-list-render"),
]
