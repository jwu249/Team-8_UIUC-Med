from django.urls import path
from .views import (
    home_page, hospital_list, hospital_list_render,
    MedServiceBaseView, MedServiceListView, MedServiceDetailView,
    service_search, chart_image,
    services_api, services_http_response, # for section 6
    api_summary_location_counts, api_summary_appointments,
    vega_chart1_page, vega_chart2_page, vega_chart_hub_page,
)

urlpatterns = [
    # a3 section 1: home page
    path("", home_page, name="home"),
    # FBV routes
    path("hospitals/manual/", hospital_list, name="hospital-list-manual"),
    path("hospitals/render/", hospital_list_render, name="hospital-list-render"),
    # CBV routes
    path("services/cbv-base/", MedServiceBaseView.as_view(), name="service-cbv-base"),
    path("services/cbv-generic/", MedServiceListView.as_view(), name="service-cbv-generic"),  # a3 section 5 GET+POST
    # a3 section 1: detail url by primary key
    path("services/<int:pk>/", MedServiceDetailView.as_view(), name="service-detail"),
    # Section 2: Search & ORM queries
    path("services/search/", service_search, name="service-search"),
    # Section 4: Data visualization
    path("services/chart/", vega_chart_hub_page, name="service-chart"),
    path("services/chart/image.png", chart_image, name="service-chart-image"),
    # A4 part 1.1 (mandatory): internal chart-ready APIs
    path("api/summary/", api_summary_location_counts, name="api-summary"),
    path("api/summary/appointments/", api_summary_appointments, name="api-summary-appointments"),
    # A4 part 1.2: dedicated Vega-Lite chart endpoints (HTML pages)
    path("vega-lite/chart1/", vega_chart1_page, name="vega-chart1"),
    path("vega-lite/chart2/", vega_chart2_page, name="vega-chart2"),
    # A3 section 6: API
    path("api/services/", services_api, name="services-api"),  # a3 section 6 JsonResponse
    path("api/services-http/", services_http_response, name="services-http")  # a3 section 6 HttpResponse demo
]
