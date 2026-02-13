from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from django.views.generic import ListView
from django.db.models import Count
from .models import MedService, User, History

import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Create your views here.

# 1 HTTPResponse (Manual)

def hospital_list(request):
    return HttpResponse("Manual Hospital List")

# 2 HTTPResponse (Render)
def hospital_list_render(request):
    return render(request, "render/hospital_list.html")


# 3 Base CBV (inherit from View)
class MedServiceBaseView(View):
    def get(self, request):
        services = MedService.objects.all()
        return render(request, "render/Service List.html", {"services": services})


# 4 Generic CBV (ListView)
class MedServiceListView(ListView):
    model = MedService
    template_name = "render/Service List.html"
    context_object_name = "services"


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
