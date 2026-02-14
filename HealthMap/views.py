from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.generic import ListView, DetailView
from django.db.models import Count
from .models import MedService, User, History

import io
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

#importing forms
from .forms import MedServiceForm

# Create your views here.

# 1 HTTPResponse (Manual)

def hospital_list(request):
    return HttpResponse("Manual Hospital List")

# 2 HTTPResponse (Render)
def hospital_list_render(request):
    return render(request, "render/hospital_list.html")

# a3 section 1: home page at "/" so root url does not 404
def home_page(request):
    return render(request, "render/home.html")


# 3 Base CBV (inherit from View)
class MedServiceBaseView(View):
    def get(self, request):
        query = request.GET.get("q", "").strip()
        services = MedService.objects.all()
        if query:
            services = services.filter(name__icontains=query)
        return render(
            request,
            "render/Service List.html",
            {"services": services, "form": MedServiceForm(), "query": query},
        )


# 4 Generic CBV (ListView)
class MedServiceListView(ListView):
    model = MedService
    template_name = "render/Service List.html"
    context_object_name = "services"

    def get_queryset(self):
        # a3 section 5: GET form search by name
        queryset = MedService.objects.all()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = MedServiceForm()
        context["query"] = self.request.GET.get("q", "").strip()
        return context

    def post(self, request, *args, **kwargs):
        # a3 section 5: POST form creates a new MedService
        form = MedServiceForm(request.POST)
        if form.is_valid():
            new_service = form.save()
            return redirect(new_service.get_absolute_url())
        self.object_list = self.get_queryset()
        context = self.get_context_data()
        context["form"] = form
        return self.render_to_response(context)


class MedServiceDetailView(DetailView):
    # a3 section 1: detail page served by pk (e.g., /services/3/)
    model = MedService
    template_name = "render/service_detail.html"
    context_object_name = "service"


# ──────────────────────────────────────────────
# Section 2: ORM Queries & Data Presentation
# ──────────────────────────────────────────────

def service_search(request):
    all_services = MedService.objects.all()

    # --- GET search: filter by location (visible in URL, bookmarkable) ---
    get_query = request.GET.get('location', '')
    get_results = None
    if get_query:
        get_results = MedService.objects.filter(location__icontains=get_query)

    # --- POST search: filter by appointments_required (hidden from URL) ---
    post_results = None
    post_filter = None
    if request.method == 'POST':
        post_filter = request.POST.get('appointments', '')
        if post_filter == 'yes':
            post_results = MedService.objects.filter(appointments_required=True)
        elif post_filter == 'no':
            post_results = MedService.objects.filter(appointments_required=False)

    # --- Relationship-spanning query: History filtered by username (uses __) ---
    username_query = request.GET.get('username', '')
    history_results = None
    if username_query:
        history_results = History.objects.filter(user__username__icontains=username_query)

    # --- Aggregations ---
    total_services = MedService.objects.count()
    services_per_location = (
        MedService.objects.values('location')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    context = {
        'all_services': all_services,
        'get_query': get_query,
        'get_results': get_results,
        'post_filter': post_filter,
        'post_results': post_results,
        'username_query': username_query,
        'history_results': history_results,
        'total_services': total_services,
        'services_per_location': services_per_location,
    }
    return render(request, 'render/search.html', context)


# ──────────────────────────────────────────────
# Section 4: Data Visualization (Matplotlib)
# ──────────────────────────────────────────────

def chart_page(request):
    return render(request, 'render/chart.html')


def chart_image(request):
    # ORM aggregation: count services per location
    data = (
        MedService.objects.values('location')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    locations = [entry['location'] for entry in data]
    counts = [entry['count'] for entry in data]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(locations, counts, color='#E84A27')
    ax.set_title('Medical Services per Location', fontsize=16)
    ax.set_xlabel('Location', fontsize=12)
    ax.set_ylabel('Number of Services', fontsize=12)
    ax.legend(bars, locations, title='Locations')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Use BytesIO to serve image from memory (no disk write)
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)  # free memory
    buf.seek(0)

    return HttpResponse(buf.read(), content_type='image/png')

def services_api(request):
    # a3 section 6: public JSON endpoint with query-param filtering
    qs = MedService.objects.all()

    name = request.GET.get("name", "").strip()
    location = request.GET.get("location", "").strip()
    appointment = request.GET.get("appointments_required", "").strip().lower()

    if name:
        qs = qs.filter(name__icontains=name)
    if location:
        qs = qs.filter(location__icontains=location)
    if appointment in {"true", "false"}:
        qs = qs.filter(appointments_required=(appointment == "true"))

    data = [
        {
            "id": s.id,
            "name": s.name,
            "location": s.location,
            "appointments_required": s.appointments_required,
        }
        for s in qs
    ]

    return JsonResponse({"count": len(data), "results": data})

def services_http_response(request):
    # a3 section 6: plain HttpResponse version to compare MIME types
    payload = {
        "note": "This endpoint uses HttpResponse, not JsonResponse.",
        "mime_type": "text/plain",
    }
    return HttpResponse(json.dumps(payload), content_type="text/plain; charset=utf-8")
