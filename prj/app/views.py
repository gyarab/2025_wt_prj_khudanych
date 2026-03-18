import unicodedata
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Count
from django.core.paginator import Paginator
from .models import Country, Region, FlagCollection
from .forms import ProfileForm


@login_required
def profile_view(request):
    """View user profile"""
    return render(request, 'profile.html', {'profile': request.user.profile})

@login_required
def profile_edit(request):
    """Edit user profile"""
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, 'profile_edit.html', {'form': form})


def _strip_accents(text: str) -> str:
    """Remove diacritics: Žilina → Zilina, São Paulo → Sao Paulo."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _accent_insensitive_match(haystack: str, needle: str) -> bool:
    """Case- and accent-insensitive substring match."""
    if not haystack or not needle:
        return False
    return _strip_accents(needle).lower() in _strip_accents(haystack).lower()

GALLERY_PER_PAGE = 60
COUNTRIES_PER_PAGE = 48

def _normalize_and_paginate(items_list, request, per_page=GALLERY_PER_PAGE):
    """Shared helper for search, normalization and pagination across views."""
    search_query = request.GET.get('search') or request.GET.get('q') or ''
    if search_query:
        search_query = search_query.strip()
        items_list = [i for i in items_list if _accent_insensitive_match(i.get('name', ''), search_query)]

    paginator = Paginator(items_list, per_page)
    page = paginator.get_page(request.GET.get('page'))
    return page, search_query

def render_homepage(request):
    """Beautiful geography-themed homepage"""
    # Get statistics
    total_countries = Country.objects.filter(status='sovereign').count()
    # Total territories is sum of Country(territory) and FlagCollection(territory)
    total_territories = (
        Country.objects.filter(status='territory').count() + 
        FlagCollection.objects.filter(category='territory').count()
    )
    total_historical = Country.objects.filter(status='historical').count() + FlagCollection.objects.filter(category='historical').count()
    total_flags = Country.objects.count() + FlagCollection.objects.count()
    total_regions = Region.objects.count()
    
    # Get featured countries (most populous sovereign states)
    featured_countries = Country.objects.filter(status='sovereign').order_by('-population')[:6]
    
    # Get all regions with sovereign country counts
    regions = Region.objects.annotate(
        country_count=Count('countries', filter=Q(countries__status='sovereign'))
    ).order_by('-country_count')
    
    context = {
        'total_countries': total_countries,
        'total_territories': total_territories,
        'total_historical': total_historical,
        'total_flags': total_flags,
        'total_regions': total_regions,
        'featured_countries': featured_countries,
        'regions': regions,
    }
    return render(request, 'home.html', context)

def countries_list(request):
    """List all sovereign countries with filtering and pagination"""
    region_filter = request.GET.get('region')
    countries_qs = Country.objects.filter(status='sovereign').select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji',
        'population', 'region__name', 'region__slug',
    )

    if region_filter:
        countries_qs = countries_qs.filter(region__slug=region_filter)

    items = []
    for c in countries_qs:
        items.append({
            'name': c.name_common,
            'cca3': c.cca3,
            'capital': c.capital,
            'img': c.flag_png,
            'emoji': c.flag_emoji,
            'region': c.region.name if c.region else '',
            'type': 'Sovereign State'
        })

    page, search_query = _normalize_and_paginate(items, request, COUNTRIES_PER_PAGE)
    regions = Region.objects.all()

    context = {
        'countries': page,
        'page_obj': page,
        'regions': regions,
        'selected_region': region_filter,
        'search_query': search_query,
        'page_title': 'Sovereign Countries',
    }
    return render(request, 'countries.html', context)

def territories_list(request):
    """List all territories and dependencies from both tables"""
    countries = Country.objects.filter(status='territory').select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji',
        'population', 'region__name', 'region__slug',
    )
    extra_territories = FlagCollection.objects.filter(category='territory').only('name', 'flag_image')

    items = []
    for c in countries:
        items.append({
            'name': c.name_common, 'cca3': c.cca3, 'img': c.flag_png,
            'emoji': c.flag_emoji, 'type': 'Major Territory', 'capital': c.capital,
            'region': c.region.name if c.region else ''
        })
    for f in extra_territories:
        items.append({'name': f.name, 'img': f.flag_image, 'type': 'Territory / Dependency'})

    page, search_query = _normalize_and_paginate(items, request, COUNTRIES_PER_PAGE)

    context = {
        'countries': page,
        'page_obj': page,
        'search_query': search_query,
        'page_title': 'Territories & Dependencies',
    }
    return render(request, 'countries.html', context)

def historical_list(request):
    """List historical flags and former countries"""
    hist_countries = Country.objects.filter(status='historical').only('name_common', 'cca3', 'flag_png', 'flag_emoji')
    hist_flags = FlagCollection.objects.filter(category='historical').only('name', 'flag_image')

    items = []
    for c in hist_countries:
        items.append({'name': c.name_common, 'img': c.flag_png, 'emoji': c.flag_emoji,
                      'link': f'/country/{c.cca3}/', 'type': 'Former Country'})
    for f in hist_flags:
        items.append({'name': f.name, 'img': f.flag_image, 'type': 'Historical Flag'})

    page, search_query = _normalize_and_paginate(items, request)

    context = {
        'page_obj': page,
        'search_query': search_query,
        'page_title': 'Historical Flags & Former States',
    }
    return render(request, 'historical_gallery.html', context)

def country_detail(request, cca3):
    """Detailed view of a single country"""
    country = get_object_or_404(Country, cca3=cca3.upper())
    
    # Get neighboring countries
    neighbors = []
    if country.borders:
        neighbors = Country.objects.filter(cca3__in=country.borders)
    
    # Get additional flags for this country with pagination
    additional_flags_qs = FlagCollection.objects.filter(country=country).order_by('name')
    paginator = Paginator(additional_flags_qs, 48)  # 48 flags per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'country': country,
        'neighbors': neighbors,
        'additional_flags': page_obj,  # This is now a page object
        'page_obj': page_obj,
    }
    return render(request, 'country_detail.html', context)


def flag_detail(request, slug):
    """SEO-friendly detail page for a specific flag with rich data parsing"""
    flag = get_object_or_404(FlagCollection, slug=slug)
    
    # Parse description JSON for rich context
    desc = flag.description if isinstance(flag.description, dict) else {}
    label_en = desc.get('label_en', '')
    native_label = desc.get('native_label', '')
    wikidata_type = desc.get('wikidata_type', '')
    
    # Construct Wikipedia search URL
    wiki_url = f"https://en.wikipedia.org/wiki/{label_en.replace(' ', '_')}" if label_en else None
    
    context = {
        'flag': flag,
        'label_en': label_en,
        'native_label': native_label,
        'wikidata_type': wikidata_type,
        'wiki_url': wiki_url,
    }
    return render(request, 'flag_detail.html', context)

def flags_gallery(request):
    """Gallery view with pagination, search, and category filter"""
    category = request.GET.get('category', 'all')

    # 1. Calculate merged counts for the category filter
    fc_counts = dict(FlagCollection.objects.values_list('category').annotate(n=Count('id')))
    c_counts = dict(Country.objects.values_list('status').annotate(n=Count('id')))
    
    pill_country_count = c_counts.get('sovereign', 0)
    pill_territory_count = c_counts.get('territory', 0) + fc_counts.get('territory', 0)
    pill_historical_count = c_counts.get('historical', 0) + fc_counts.get('historical', 0)
    total_flags = Country.objects.count() + FlagCollection.objects.count()

    cat_counts = {
        'state': fc_counts.get('state', 0),
        'city': fc_counts.get('city', 0),
        'region': fc_counts.get('region', 0),
        'international': fc_counts.get('international', 0),
        'territory': pill_territory_count,
        'historical': pill_historical_count,
        'country': pill_country_count,
    }

    items = []

    # 2. Gather countries
    show_countries = category in ('all', 'country', 'territory', 'historical')
    if show_countries:
        country_filter = Q()
        if category == 'country': country_filter = Q(status='sovereign')
        elif category == 'territory': country_filter = Q(status='territory')
        elif category == 'historical': country_filter = Q(status='historical')
        
        qs = Country.objects.filter(country_filter).only('name_common', 'cca3', 'flag_png', 'flag_emoji', 'status')
        for c in qs:
            items.append({
                'name': c.name_common, 'img': c.flag_png, 'emoji': c.flag_emoji,
                'link': f'/country/{c.cca3}/',
                'badge': 'Country' if c.status == 'sovereign' else c.get_status_display(),
            })

    # 3. Gather extras
    if category != 'country':
        qs = FlagCollection.objects.only('name', 'flag_image', 'category')
        if category != 'all':
            qs = qs.filter(category=category)
        for f in qs:
            items.append({
                'name': f.name, 'img': f.flag_image, 'badge': f.get_category_display()
            })

    page, search_query = _normalize_and_paginate(items, request)

    context = {
        'page_obj': page,
        'selected_category': category,
        'search_query': search_query,
        'cat_counts': cat_counts,
        'total_flags': total_flags,
    }
    return render(request, 'flags_gallery.html', context)

def render_about(request):
    """About page"""
    return render(request, 'about.html')
