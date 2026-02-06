from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from django.views.generic import ListView
from .models import MedService

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
