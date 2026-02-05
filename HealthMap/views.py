from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

# 1 HTTPResponse (Manual)

def hospital_list(request):
    return HttpResponse("Manual Hospital List")

# 2 HTTPResponse (Render)
def hospital_list_render(request):
    return render(request, "render/hospital_list.html")
