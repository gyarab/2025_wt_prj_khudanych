from django.shortcuts import render, HttpResponse

from .models import CountryFlag

# Create your views here.
def home(request):
    return render(request, "home.html")

def flags(request):
    flags = CountryFlag.objects.all()
    return render(request, "flags.html", {"flags": flags})