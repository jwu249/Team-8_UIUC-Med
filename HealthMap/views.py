from django.shortcuts import render
from django.http import HttpResponse
from django.views import View
from django.views.generic import ListView
from .models import MedService

#importing forms
from .forms import MedServiceForm

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

    def get_queryset(self): # get
        queryset = super().get_queryset()
        query = self.request.GET.get("q")

        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset

    def get_context_data(self, **kwargs): # adds form to page
        context = super().get_context_data(**kwargs)
        context["form"] = MedServiceForm()
        return context

    def post(self, request, *args, **kwargs): # creates new MedService
        form = MedServiceForm(request.POST)

        if form.is_valid():
            form.save()
        return self.get(request, *args, **kwargs)
