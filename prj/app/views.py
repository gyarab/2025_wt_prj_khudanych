from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count
from .models import Country, Region, FlagCollection

def render_homepage(request):
    """Beautiful geography-themed homepage"""
    # Get statistics
    total_countries = Country.objects.count()
    total_flags = total_countries + FlagCollection.objects.count()
    total_regions = Region.objects.count()
    
    # Get featured countries (most populous)
    featured_countries = Country.objects.order_by('-population')[:6]
    
    # Get all regions with country counts
    regions = Region.objects.annotate(country_count=Count('countries')).order_by('-country_count')
    
    context = {
        'total_countries': total_countries,
        'total_flags': total_flags,
        'total_regions': total_regions,
        'featured_countries': featured_countries,
        'regions': regions,
    }
    return render(request, 'home.html', context)

def countries_list(request):
    """List all countries with filtering"""
    countries = Country.objects.select_related('region').all()
    
    # Filtering
    region_filter = request.GET.get('region')
    search_query = request.GET.get('search')
    
    if region_filter:
        countries = countries.filter(region__slug=region_filter)
    
    if search_query:
        countries = countries.filter(
            Q(name_common__icontains=search_query) |
            Q(name_official__icontains=search_query) |
            Q(capital__icontains=search_query)
        )
    
    regions = Region.objects.all()
    
    context = {
        'countries': countries,
        'regions': regions,
        'selected_region': region_filter,
        'search_query': search_query,
    }
    return render(request, 'countries.html', context)

def country_detail(request, cca3):
    """Detailed view of a single country"""
    country = get_object_or_404(Country, cca3=cca3.upper())
    
    # Get neighboring countries
    neighbors = []
    if country.borders:
        neighbors = Country.objects.filter(cca3__in=country.borders)
    
    # Get additional flags for this country
    additional_flags = FlagCollection.objects.filter(country=country)
    
    context = {
        'country': country,
        'neighbors': neighbors,
        'additional_flags': additional_flags,
    }
    return render(request, 'country_detail.html', context)

def flags_gallery(request):
    """Gallery view of all flags"""
    category = request.GET.get('category', 'all')
    
    countries = Country.objects.all()
    additional_flags = FlagCollection.objects.all()
    
    if category != 'all':
        additional_flags = additional_flags.filter(category=category)
    
    context = {
        'countries': countries,
        'additional_flags': additional_flags,
        'selected_category': category,
    }
    return render(request, 'flags_gallery.html', context)

def render_about(request):
    """About page"""
    return render(request, 'about.html')