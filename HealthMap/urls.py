from django.urls import path
from .views import hospital_list, hospital_list_render, MedServiceBaseView, MedServiceListView

urlpatterns = [
    # FBV routes
    path("hospitals/manual/", hospital_list, name="hospital-list-manual"),
    path("hospitals/render/", hospital_list_render, name="hospital-list-render"),
    # CBV routes
    path("services/cbv-base/", MedServiceBaseView.as_view(), name="service-cbv-base"),
    path("services/cbv-generic/", MedServiceListView.as_view(), name="service-cbv-generic"),
]
