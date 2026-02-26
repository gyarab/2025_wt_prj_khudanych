import unicodedata
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Country, Region, FlagCollection


def _strip_accents(text: str) -> str:
    """Remove diacritics: Žilina → Zilina, São Paulo → Sao Paulo."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _accent_insensitive_match(haystack: str, needle: str) -> bool:
    """Case- and accent-insensitive substring match."""
    return _strip_accents(needle).lower() in _strip_accents(haystack).lower()

GALLERY_PER_PAGE = 60
COUNTRIES_PER_PAGE = 48

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
    """List all countries with filtering and pagination"""
    countries = Country.objects.select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji',
        'population', 'region__name', 'region__slug',
    )

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

    paginator = Paginator(countries, COUNTRIES_PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))
    regions = Region.objects.all()

    context = {
        'countries': page,
        'page_obj': page,
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
    """Gallery view with pagination, search, and category filter"""
    category = request.GET.get('category', 'all')
    search_query = request.GET.get('q', '').strip()

    # Category counts (cached per request, quick aggregate)
    cat_counts = dict(
        FlagCollection.objects.values_list('category')
        .annotate(n=Count('id')).values_list('category', 'n')
    )
    country_count = Country.objects.count()
    fc_total = sum(cat_counts.values())
    total_flags = country_count + fc_total

    # Build a unified list of dicts for the template so we can paginate
    # everything together instead of two separate querysets.
    items = []  # list of lightweight dicts: {name, url, link, type}

    show_countries = category in ('all', 'country')
    show_extras = category != 'country'

    if show_countries:
        qs = Country.objects.only('name_common', 'cca3', 'flag_png', 'flag_emoji')
        if search_query:
            # Try SQL first for exact/ascii matches; fall back to Python for accents
            qs_sql = qs.filter(name_common__icontains=search_query)
            if qs_sql.exists():
                qs = qs_sql
            else:
                # Accent-insensitive: filter in Python (fast for ~260 countries)
                qs = [c for c in qs if _accent_insensitive_match(c.name_common, search_query)]
        for c in qs:
            items.append({
                'name': c.name_common,
                'img': c.flag_png,
                'emoji': c.flag_emoji,
                'link': f'/country/{c.cca3}/',
                'badge': 'Country',
            })

    if show_extras:
        qs = FlagCollection.objects.only('name', 'flag_image', 'category')
        if category not in ('all', 'country'):
            qs = qs.filter(category=category)
        if search_query:
            # Try SQL first; fall back to Python for accent-insensitive
            qs_sql = qs.filter(name__icontains=search_query)
            if qs_sql.exists():
                qs = qs_sql
            else:
                qs = [f for f in qs if _accent_insensitive_match(f.name, search_query)]
        for f in qs:
            items.append({
                'name': f.name,
                'img': f.flag_image,
                'emoji': '',
                'link': '',
                'badge': f.get_category_display(),
            })

    paginator = Paginator(items, GALLERY_PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page,
        'selected_category': category,
        'search_query': search_query,
        'cat_counts': cat_counts,
        'country_count': country_count,
        'total_flags': total_flags,
    }
    return render(request, 'flags_gallery.html', context)

def render_about(request):
    """About page"""
    return render(request, 'about.html')