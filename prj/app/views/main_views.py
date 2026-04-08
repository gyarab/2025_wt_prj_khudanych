"""
Main view functions for the Just Enough Flags application.
This module contains primary route handlers for homepage, country details,
flag details, and profile management.
"""

from urllib.parse import quote
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q, Count, Case, When, IntegerField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _, get_language

from ..models import Country, Region, FlagCollection
from ..forms import ProfileForm
from .eligibility import (
    is_country_detail_eligible,
    is_territory_detail_eligible,
    get_territory_owner_country
)
from .search_filters import country_detail_quality_filter, build_country_search_filter
from .text_utils import normalize_query
from .pagination_helpers import (
    build_flag_navigation_context,
    COUNTRIES_PER_PAGE
)


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


def render_homepage(request):
    """Beautiful geography-themed homepage"""
    sovereign_countries = [c for c in Country.objects.filter(status='sovereign').select_related('region') if is_country_detail_eligible(c)]
    territory_countries = [c for c in Country.objects.filter(status='territory').select_related('region') if is_territory_detail_eligible(c)]
    historical_countries = [c for c in Country.objects.filter(status='historical').select_related('region') if is_country_detail_eligible(c)]

    total_countries = len(sovereign_countries)
    # Fixed: Use consistent counting for territories/dependencies
    total_territories = len(territory_countries)
    dependency_flags = FlagCollection.objects.filter(category='dependency', is_public=True).count()
    total_territories += dependency_flags
    
    total_historical = len(historical_countries) + FlagCollection.objects.filter(category='historical', is_public=True).count()
    total_flags = Country.objects.count() + FlagCollection.objects.filter(is_public=True).count()
    total_regions = Region.objects.count()
    
    featured_countries = sorted(sovereign_countries, key=lambda c: c.population, reverse=True)[:6]
    
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
    """List sovereign countries with DB-level pagination and instant search support."""
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    normalized_search_query = normalize_query(search_query)
    region_filter = request.GET.get('region')

    # 1. OPRAVA: Odstraněno .only(), takže Django načte i populaci, rozlohu atd.
    countries_qs = Country.objects.filter(status='sovereign').filter(
        country_detail_quality_filter()
    ).select_related('region').order_by('name_common')

    if region_filter:
        countries_qs = countries_qs.filter(region__slug=region_filter)

    if normalized_search_query:
        countries_qs = countries_qs.filter(build_country_search_filter(normalized_search_query))

    paginator = Paginator(countries_qs, COUNTRIES_PER_PAGE)
    page_obj = paginator.get_page(page_number)

    # 2. OPRAVA: Místo destrukce objektů na slovníky jim jen přidáme potřebný 'link' a aliasy
    for c in page_obj.object_list:
        c.link = reverse('country_detail', kwargs={'cca3': c.cca3})
        c.type = _('Sovereign State')
        # Přidáme aliasy, aby šablona nepadala při hledání starých názvů klíčů
        c.img = c.flag_png
        c.emoji = c.flag_emoji
        c.name = c.name_common

    regions = Region.objects.all()

    context = {
        'countries': page_obj,
        'page_obj': page_obj,
        'regions': regions,
        'selected_region': region_filter,
        'search_query': search_query,
        'search_api_url': reverse('countries_search_api'),
        'search_placeholder': _('Search countries...'),
        'page_title': _('Sovereign Countries'),
    }
    return render(request, 'countries.html', context)


def country_detail(request, cca3):
    """Detailed view of a single country"""
    country = get_object_or_404(Country, cca3=cca3.upper())
    if not is_country_detail_eligible(country):
        if country.status == 'territory':
            return redirect('territory_detail', cca3=country.cca3)
        if country.status == 'historical':
            return redirect('historical')
        return redirect('countries')
    
    neighbors = []
    if country.borders:
        neighbor_candidates = Country.objects.filter(cca3__in=country.borders)
        neighbors = [n for n in neighbor_candidates if is_country_detail_eligible(n)]
    
    # Fetch the main flag for this country from FlagCollection
    main_flag = country.additional_flags.filter(
        category__in=['country', 'dependency'],
        is_public=True
    ).first()
    
    # Get dependencies/territories
    dependencies = country.dependencies.filter(status='territory').order_by('name_common')
    
    # Exclude national flags (category='country') and dependencies to avoid duplication
    # Dependencies are shown in the "Dependencies & Territories" section
    # Sort dependencies first, then regions, cities, historical
    additional_flags_qs = FlagCollection.objects.filter(
        country=country, 
        is_public=True
    ).exclude(
        category__in=['country', 'dependency']
    ).select_related(
        'country'
    ).annotate(
        sort_priority=Case(
            When(category='dependency', then=1),
            When(category='region', then=2),
            When(category='city', then=3),
            When(category='historical', then=4),
            When(category='international', then=5),
            default=6,
            output_field=IntegerField()
        )
    ).order_by('sort_priority', 'name')
    paginator = Paginator(additional_flags_qs, 48)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'country': country,
        'neighbors': neighbors,
        'main_flag': main_flag,
        'dependencies': dependencies,
        'additional_flags': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'country_detail.html', context)


def territory_detail(request, cca3):
    """Detailed view of a single territory with owner information."""
    territory = get_object_or_404(Country, cca3=cca3.upper(), status='territory')
    if not is_territory_detail_eligible(territory):
        return redirect('territories')

    # Use database relationship first, fallback to function
    owner_country = territory.owner
    if not owner_country:
        owner_country = get_territory_owner_country(territory)
    
    # Fetch the main flag for this territory from FlagCollection
    main_flag = territory.additional_flags.filter(
        category__in=['country', 'dependency'],
        is_public=True
    ).first()

    # Exclude national flags (category='country') to avoid duplication
    # Sort dependencies first, then regions, cities, historical
    additional_flags_qs = FlagCollection.objects.filter(
        country=territory, 
        is_public=True
    ).exclude(
        category='country'
    ).annotate(
        sort_priority=Case(
            When(category='dependency', then=1),
            When(category='region', then=2),
            When(category='city', then=3),
            When(category='historical', then=4),
            When(category='international', then=5),
            default=6,
            output_field=IntegerField()
        )
    ).order_by('sort_priority', 'name')
    paginator = Paginator(additional_flags_qs, 48)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'territory': territory,
        'owner_country': owner_country,
        'main_flag': main_flag,
        'additional_flags': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'territory_detail.html', context)


def flag_detail(request, category, slug):
    """Detail page for a specific flag using category + slug URL."""
    flag = get_object_or_404(FlagCollection.objects.select_related('country'), slug=slug, is_public=True)
    if category != flag.category:
        return redirect('flag_detail', category=flag.category, slug=flag.slug)

    desc = flag.description if isinstance(flag.description, dict) else {}

    wikidata_type_raw = desc.get('wikidata_type', '')
    if isinstance(wikidata_type_raw, str):
        wikidata_type_list = [p.strip() for p in wikidata_type_raw.split(',') if p.strip()]
    elif isinstance(wikidata_type_raw, list):
        wikidata_type_list = [str(p).strip() for p in wikidata_type_raw if str(p).strip()]
    else:
        wikidata_type_list = []

    native_names = []
    for key in ('native_wiki_titles', 'label_native', 'native_label'):
        value = desc.get(key)
        if isinstance(value, list):
            native_names.extend([str(v).strip() for v in value if str(v).strip()])
        elif isinstance(value, str) and value.strip():
            native_names.extend([p.strip() for p in value.split('||') if p.strip()])
    native_names = list(dict.fromkeys(native_names))

    area_km2 = flag.area_km2
    population = flag.population
    latitude = flag.latitude
    longitude = flag.longitude

    has_area_km2 = area_km2 is not None
    has_population = population is not None
    has_coordinates = latitude is not None and longitude is not None

    label_en = desc.get('label_en', '') if isinstance(desc.get('label_en', ''), str) else ''
    wiki_label = label_en.strip() or flag.name
    wiki_url = None
    if wiki_label and not (wiki_label.startswith('Q') and wiki_label[1:].isdigit()):
        wiki_url = f"https://en.wikipedia.org/wiki/{quote(wiki_label.replace(' ', '_'))}"

    current_lang = get_language() or 'en'

    localized_description = desc.get(current_lang) or desc.get('en', '')
    navigation_context = build_flag_navigation_context(flag, request)
    
    context = {
        'flag': flag,
        'native_names': native_names,
        'wikidata_type_list': wikidata_type_list,
        'population': population,
        'area_km2': area_km2,
        'latitude': latitude,
        'longitude': longitude,
        'has_area_km2': has_area_km2,
        'has_population': has_population,
        'has_coordinates': has_coordinates,
        'wiki_url': wiki_url,
        'localized_description': localized_description,
        **navigation_context,
    }
    return render(request, 'flag_detail.html', context)


def render_about(request):
    """About page"""
    return render(request, 'about.html')
