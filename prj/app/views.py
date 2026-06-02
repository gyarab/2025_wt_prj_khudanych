from django.shortcuts import render, HttpResponse
from .models import Country

# Create your views here.
def home(request):
    return render(request, "home.html")

def flags(request):
    flags = Country.objects.all()
    return render(request, "flags.html", {"flags": flags})
def api_playground(request):
    return render(request, "api_playground.html")