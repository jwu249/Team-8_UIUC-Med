from django.urls import path
from .views import (
    hospital_list, hospital_list_render,
    MedServiceBaseView, MedServiceListView,
    service_search, chart_page, chart_image,
)

urlpatterns = [
    # FBV routes
    path("hospitals/manual/", hospital_list, name="hospital-list-manual"),
    path("hospitals/render/", hospital_list_render, name="hospital-list-render"),
    # CBV routes
    path("services/cbv-base/", MedServiceBaseView.as_view(), name="service-cbv-base"),
    path("services/cbv-generic/", MedServiceListView.as_view(), name="service-cbv-generic"),
    # Section 2: Search & ORM queries
    path("services/search/", service_search, name="service-search"),
    # Section 4: Data visualization
    path("services/chart/", chart_page, name="service-chart"),
    path("services/chart/image.png", chart_image, name="service-chart-image"),
]
