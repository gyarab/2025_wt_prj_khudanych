from urllib.parse import quote, urlencode
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import Country, Region, FlagCollection
from .forms import ProfileForm
from itertools import chain

# Import naší bleskové zkompilované Rust knihovny
import flag_search_core


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
    """Remove diacritics using Rust extension."""
    return flag_search_core.strip_accents(text)


def _accent_insensitive_match(haystack: str, needle: str) -> bool:
    """Case- and accent-insensitive substring match using Rust extension."""
    return flag_search_core.accent_insensitive_match(haystack, needle)


def _has_complete_country_template_data(country: Country) -> bool:
    """Check whether a country has complete data required by detail templates."""
    if not country:
        return False

    has_required_identity = bool(country.name_common and country.name_official and country.cca2 and country.cca3)
    has_required_flag = bool(country.flag_emoji and (country.flag_svg or country.flag_png))
    has_required_geo = bool(country.capital and country.region and country.area is not None)
    has_required_population = bool(country.population and country.population > 0)
    has_required_currencies = isinstance(country.currencies, dict) and bool(country.currencies)
    has_required_languages = isinstance(country.languages, dict) and bool(country.languages)

    return all([
        has_required_identity,
        has_required_flag,
        has_required_geo,
        has_required_population,
        has_required_currencies,
        has_required_languages,
    ])


def _is_country_detail_eligible(country: Country) -> bool:
    """Country detail pages are for sovereign/historical records with complete data."""
    return bool(country and country.status in ('sovereign', 'historical') and _has_complete_country_template_data(country))


def _is_territory_detail_eligible(country: Country) -> bool:
    """Territory detail pages are for territory records with complete data."""
    return bool(country and country.status == 'territory' and _has_complete_country_template_data(country))


TERRITORY_OWNER_BY_CCA3 = {
    # United Kingdom
    'AIA': 'GBR', 'BMU': 'GBR', 'CYM': 'GBR', 'FLK': 'GBR', 'GGY': 'GBR', 'GIB': 'GBR',
    'IMN': 'GBR', 'JEY': 'GBR', 'MSR': 'GBR', 'PCN': 'GBR', 'SGS': 'GBR', 'TCA': 'GBR', 'VGB': 'GBR',
    # France
    'BLM': 'FRA', 'GUF': 'FRA', 'GLP': 'FRA', 'MAF': 'FRA', 'MTQ': 'FRA', 'MYT': 'FRA',
    'NCL': 'FRA', 'PYF': 'FRA', 'REU': 'FRA', 'SPM': 'FRA', 'WLF': 'FRA',
    # United States
    'ASM': 'USA', 'GUM': 'USA', 'MNP': 'USA', 'PRI': 'USA', 'UMI': 'USA', 'VIR': 'USA',
    # Netherlands
    'ABW': 'NLD', 'CUW': 'NLD', 'SXM': 'NLD', 'ANT': 'NLD',
    # China
    'HKG': 'CHN', 'MAC': 'CHN',
    # Denmark
    'FRO': 'DNK', 'GRL': 'DNK',
    # New Zealand
    'COK': 'NZL', 'NIU': 'NZL', 'TKL': 'NZL',
    # Australia
    'CXR': 'AUS', 'CCK': 'AUS', 'NFK': 'AUS',
    # Morocco
    'ESH': 'MAR',
}


def _get_territory_owner_country(territory: Country):
    """Resolve the sovereign owner country for a territory using Rust optimization."""
    # Rychlý lookup přes slovník O(1)
    owner_cca3 = TERRITORY_OWNER_BY_CCA3.get(territory.cca3)
    
    if not owner_cca3:
        # Nasazení Rustu pro náročné prohledávání podřetězců
        text = f"{territory.name_common or ''} {territory.name_official or ''}"
        owner_cca3 = flag_search_core.identify_owner_cca3(text)

    if owner_cca3:
        owner = Country.objects.filter(cca3=owner_cca3).first()
        if owner and _is_country_detail_eligible(owner):
            return owner

    return None


GALLERY_PER_PAGE = 60
COUNTRIES_PER_PAGE = 48


class CountOnlyPaginator(Paginator):
    """Paginator backed by an explicit count without materializing full item lists."""

    def __init__(self, count, per_page):
        self._count = count
        super().__init__([], per_page)

    @property
    def count(self):
        return self._count


def _country_detail_quality_filter():
    """Database-level constraints mirroring country/territory detail data requirements."""
    return (
        Q(name_common__isnull=False) & ~Q(name_common='') &
        Q(name_official__isnull=False) & ~Q(name_official='') &
        Q(cca2__isnull=False) & ~Q(cca2='') &
        Q(cca3__isnull=False) & ~Q(cca3='') &
        Q(flag_emoji__isnull=False) & ~Q(flag_emoji='') &
        (Q(flag_svg__isnull=False) & ~Q(flag_svg='') | Q(flag_png__isnull=False) & ~Q(flag_png='')) &
        Q(capital__isnull=False) & ~Q(capital='') &
        Q(region__isnull=False) &
        Q(area__isnull=False) &
        Q(population__gt=0) &
        Q(currencies__isnull=False) &
        ~Q(currencies={}) &
        Q(languages__isnull=False)
        & ~Q(languages={})
    )


def _build_country_search_filter(search_query, *field_names):
    """Build DB filter for search text and its accent-stripped variant."""
    if not search_query:
        return Q()

    search_filter = Q()
    for field_name in field_names:
        search_filter |= Q(**{f"{field_name}__icontains": search_query})

    stripped_query = _strip_accents(search_query)
    if stripped_query and stripped_query != search_query:
        for field_name in field_names:
            search_filter |= Q(**{f"{field_name}__icontains": stripped_query})

    return search_filter


def _build_flag_name_search_filter(search_query):
    """Accent-insensitive DB filter for flag names."""
    if not search_query:
        return Q()

    search_filter = Q(name__icontains=search_query)
    stripped_query = _strip_accents(search_query)
    if stripped_query and stripped_query != search_query:
        search_filter |= Q(name__icontains=stripped_query)
    return search_filter


def _with_query_params(url, params):
    """Append query params to URL while skipping empty values."""
    clean_params = {k: v for k, v in params.items() if v not in (None, '')}
    if not clean_params:
        return url
    return f"{url}?{urlencode(clean_params)}"


def _build_flag_detail_link(flag, source='', search_query='', page=None, gallery_category=''):
    """Create detail URL with optional source context used for prev/next navigation."""
    base_url = reverse('flag_detail', kwargs={'category': flag.category, 'slug': flag.slug})
    return _with_query_params(base_url, {
        'src': source,
        'q': search_query,
        'page': page,
        'gallery_category': gallery_category,
    })


def _build_flag_navigation_context(flag, request):
    """Build contextual previous/next links for flag detail pages."""
    src = (request.GET.get('src') or '').strip()
    search_query = (request.GET.get('q') or '').strip()
    page = (request.GET.get('page') or '').strip()
    page = page if page.isdigit() else ''
    gallery_category = (request.GET.get('gallery_category') or '').strip()

    qs = FlagCollection.objects.filter(is_public=True)

    if src.startswith('country:'):
        cca3 = src.split(':', 1)[1].upper().strip()
        qs = qs.filter(country__cca3=cca3)
    elif src.startswith('territory:'):
        cca3 = src.split(':', 1)[1].upper().strip()
        qs = qs.filter(country__cca3=cca3)
    elif src == 'historical':
        qs = qs.filter(category='historical')
        if search_query:
            qs = qs.filter(_build_flag_name_search_filter(search_query))
    elif src == 'gallery':
        if gallery_category and gallery_category != 'all':
            qs = qs.filter(category=gallery_category)
        if search_query:
            qs = qs.filter(_build_flag_name_search_filter(search_query))
    else:
        qs = qs.filter(category=flag.category)

    qs = qs.order_by('name', 'id')

    prev_flag = qs.filter(
        Q(name__lt=flag.name) |
        (Q(name=flag.name) & Q(id__lt=flag.id))
    ).order_by('-name', '-id').first()

    next_flag = qs.filter(
        Q(name__gt=flag.name) |
        (Q(name=flag.name) & Q(id__gt=flag.id))
    ).order_by('name', 'id').first()

    nav_params = {
        'src': src,
        'q': search_query,
        'page': page,
        'gallery_category': gallery_category,
    }

    prev_flag_url = _with_query_params(
        reverse('flag_detail', kwargs={'category': prev_flag.category, 'slug': prev_flag.slug}),
        nav_params,
    ) if prev_flag else None

    next_flag_url = _with_query_params(
        reverse('flag_detail', kwargs={'category': next_flag.category, 'slug': next_flag.slug}),
        nav_params,
    ) if next_flag else None

    back_url = None
    if src == 'gallery':
        back_url = _with_query_params(reverse('flags_gallery'), {
            'category': gallery_category or 'all',
            'q': search_query,
            'page': page,
        })
    elif src == 'historical':
        back_url = _with_query_params(reverse('historical'), {
            'q': search_query,
            'page': page,
        })
    elif src.startswith('country:'):
        cca3 = src.split(':', 1)[1].upper().strip()
        back_url = reverse('country_detail', kwargs={'cca3': cca3})
        if page:
            back_url = f"{back_url}?page={page}#flags"
        else:
            back_url = f"{back_url}#flags"
    elif src.startswith('territory:'):
        cca3 = src.split(':', 1)[1].upper().strip()
        back_url = reverse('territory_detail', kwargs={'cca3': cca3})
        if page:
            back_url = f"{back_url}?page={page}#flags"
        else:
            back_url = f"{back_url}#flags"

    return {
        'prev_flag': prev_flag,
        'next_flag': next_flag,
        'prev_flag_url': prev_flag_url,
        'next_flag_url': next_flag_url,
        'back_url': back_url,
    }


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
    sovereign_countries = [c for c in Country.objects.filter(status='sovereign').select_related('region') if _is_country_detail_eligible(c)]
    territory_countries = [c for c in Country.objects.filter(status='territory').select_related('region') if _is_territory_detail_eligible(c)]
    historical_countries = [c for c in Country.objects.filter(status='historical').select_related('region') if _is_country_detail_eligible(c)]

    # Homepage counters should match what users can actually open (filtered by is_public=True).
    total_countries = len(sovereign_countries)
    total_territories = len(territory_countries) + FlagCollection.objects.filter(category='territory', is_public=True).count()
    total_historical = len(historical_countries) + FlagCollection.objects.filter(category='historical', is_public=True).count()
    total_flags = Country.objects.count() + FlagCollection.objects.filter(is_public=True).count()
    total_regions = Region.objects.count()
    
    # Get featured countries
    featured_countries = sorted(sovereign_countries, key=lambda c: c.population, reverse=True)[:6]
    
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
    """List sovereign countries with DB-level pagination and instant search support."""
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    region_filter = request.GET.get('region')

    countries_qs = Country.objects.filter(status='sovereign').filter(
        _country_detail_quality_filter()
    ).select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji', 'region__name', 'region__slug',
    ).order_by('name_common')

    if region_filter:
        countries_qs = countries_qs.filter(region__slug=region_filter)

    if search_query:
        countries_qs = countries_qs.filter(_build_country_search_filter(search_query, 'name_common', 'capital'))

    paginator = Paginator(countries_qs, COUNTRIES_PER_PAGE)
    page_obj = paginator.get_page(page_number)

    page_items = []
    for c in page_obj.object_list:
        page_items.append({
            'name': c.name_common,
            'cca3': c.cca3,
            'link': reverse('country_detail', kwargs={'cca3': c.cca3}),
            'capital': c.capital,
            'img': c.flag_png,
            'emoji': c.flag_emoji,
            'region': c.region.name if c.region else '',
            'type': _('Sovereign State')
        })
    page_obj.object_list = page_items

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


def territories_list(request):
    """List territories and dependencies with DB-level pagination and instant search."""
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    per_page = COUNTRIES_PER_PAGE

    territory_qs = Country.objects.filter(status='territory').filter(
        _country_detail_quality_filter()
    ).select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji', 'region__name',
    ).order_by('name_common')

    if search_query:
        territory_qs = territory_qs.filter(_build_country_search_filter(search_query, 'name_common', 'capital'))

    extra_territories_qs = FlagCollection.objects.filter(
        category='territory',
        is_public=True,
    ).only('name', 'flag_image').order_by('name')
    if search_query:
        stripped_query = _strip_accents(search_query)
        extra_filter = Q(name__icontains=search_query)
        if stripped_query and stripped_query != search_query:
            extra_filter |= Q(name__icontains=stripped_query)
        extra_territories_qs = extra_territories_qs.filter(extra_filter)

    total_territories_count = territory_qs.count()
    total_extra_count = extra_territories_qs.count()
    total_combined = total_territories_count + total_extra_count

    start_index = (page_number - 1) * per_page
    end_index = start_index + per_page

    items_to_display = []

    if start_index < total_territories_count:
        territory_items = territory_qs[start_index:end_index]
        for c in territory_items:
            items_to_display.append({
                'name': c.name_common,
                'cca3': c.cca3,
                'link': reverse('territory_detail', kwargs={'cca3': c.cca3}),
                'img': c.flag_png,
                'emoji': c.flag_emoji,
                'type': _('Major Territory'),
                'capital': c.capital,
                'region': c.region.name if c.region else '',
            })

        remaining_slots = per_page - len(items_to_display)
        if remaining_slots > 0:
            for f in extra_territories_qs[:remaining_slots]:
                items_to_display.append({
                    'name': f.name,
                    'img': f.flag_image,
                    'type': _('Territory / Dependency'),
                    'link': _build_flag_detail_link(
                        f,
                        source='gallery',
                        search_query=search_query,
                        page=page_number,
                        gallery_category='territory',
                    ),
                })
    else:
        db_offset = start_index - total_territories_count
        for f in extra_territories_qs[db_offset:db_offset + per_page]:
            items_to_display.append({
                'name': f.name,
                'img': f.flag_image,
                'type': _('Territory / Dependency'),
                'link': _build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    page=page_number,
                    gallery_category='territory',
                ),
            })

    paginator = CountOnlyPaginator(total_combined, per_page)
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = items_to_display

    context = {
        'countries': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'search_api_url': reverse('territories_search_api'),
        'search_placeholder': _('Search territories...'),
        'page_title': _('Territories & Dependencies'),
        'compact_territory_cards': True,
    }
    return render(request, 'countries.html', context)


def historical_list(request):
    """List historical countries and flags with DB-level pagination and instant search."""
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    per_page = GALLERY_PER_PAGE

    historical_country_qs = Country.objects.filter(status='historical').filter(
        _country_detail_quality_filter()
    ).only('name_common', 'cca3', 'flag_png', 'flag_emoji').order_by('name_common')

    if search_query:
        historical_country_qs = historical_country_qs.filter(_build_country_search_filter(search_query, 'name_common'))

    historical_flag_qs = FlagCollection.objects.filter(
        category='historical',
        is_public=True,
    ).only('name', 'flag_image').order_by('name')

    if search_query:
        stripped_query = _strip_accents(search_query)
        hist_filter = Q(name__icontains=search_query)
        if stripped_query and stripped_query != search_query:
            hist_filter |= Q(name__icontains=stripped_query)
        historical_flag_qs = historical_flag_qs.filter(hist_filter)

    total_countries_count = historical_country_qs.count()
    total_flags_count = historical_flag_qs.count()
    total_combined = total_countries_count + total_flags_count

    start_index = (page_number - 1) * per_page
    end_index = start_index + per_page

    items_to_display = []

    if start_index < total_countries_count:
        for c in historical_country_qs[start_index:end_index]:
            items_to_display.append({
                'name': c.name_common,
                'img': c.flag_png,
                'emoji': c.flag_emoji,
                'link': reverse('country_detail', kwargs={'cca3': c.cca3}),
                'type': _('Former Country'),
            })

        remaining_slots = per_page - len(items_to_display)
        if remaining_slots > 0:
            for f in historical_flag_qs[:remaining_slots]:
                items_to_display.append({
                    'name': f.name,
                    'img': f.flag_image,
                    'type': _('Historical Flag'),
                    'link': _build_flag_detail_link(
                        f,
                        source='historical',
                        search_query=search_query,
                        page=page_number,
                    ),
                })
    else:
        db_offset = start_index - total_countries_count
        for f in historical_flag_qs[db_offset:db_offset + per_page]:
            items_to_display.append({
                'name': f.name,
                'img': f.flag_image,
                'type': _('Historical Flag'),
                'link': _build_flag_detail_link(
                    f,
                    source='historical',
                    search_query=search_query,
                    page=page_number,
                ),
            })

    paginator = CountOnlyPaginator(total_combined, per_page)
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = items_to_display

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'search_api_url': reverse('historical_search_api'),
        'page_title': _('Historical Flags & Former States'),
    }
    return render(request, 'historical_gallery.html', context)


def country_detail(request, cca3):
    """Detailed view of a single country"""
    country = get_object_or_404(Country, cca3=cca3.upper())
    if not _is_country_detail_eligible(country):
        if country.status == 'territory':
            return redirect('territory_detail', cca3=country.cca3)
        if country.status == 'historical':
            return redirect('historical')
        return redirect('countries')
    
    neighbors = []
    if country.borders:
        neighbor_candidates = Country.objects.filter(cca3__in=country.borders)
        neighbors = [n for n in neighbor_candidates if _is_country_detail_eligible(n)]
    
    # Added is_public=True filter
    additional_flags_qs = FlagCollection.objects.filter(country=country, is_public=True).order_by('name')
    paginator = Paginator(additional_flags_qs, 48)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'country': country,
        'neighbors': neighbors,
        'additional_flags': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'country_detail.html', context)


def territory_detail(request, cca3):
    """Detailed view of a single territory with owner information."""
    territory = get_object_or_404(Country, cca3=cca3.upper(), status='territory')
    if not _is_territory_detail_eligible(territory):
        return redirect('territories')

    owner_country = _get_territory_owner_country(territory)

    # Added is_public=True filter
    additional_flags_qs = FlagCollection.objects.filter(country=territory, is_public=True).order_by('name')
    paginator = Paginator(additional_flags_qs, 48)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'territory': territory,
        'owner_country': owner_country,
        'additional_flags': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'territory_detail.html', context)


def _collect_gallery_querysets(category, search_query=''):
    country_qs = Country.objects.none()
    flag_qs = FlagCollection.objects.none()

    show_countries = category in ('all', 'country', 'territory', 'historical')
    
    if show_countries:
        if category == 'country':
            allowed_statuses = ['sovereign']
        elif category == 'territory':
            allowed_statuses = ['territory']
        elif category == 'historical':
            allowed_statuses = ['historical']
        else:
            # The gallery should expose only records with dedicated detail routes.
            allowed_statuses = ['sovereign', 'territory', 'historical']

        country_filter = Q(status__in=allowed_statuses)

        if search_query:
            country_filter &= Q(name_common__icontains=search_query)

        country_qs = Country.objects.filter(country_filter).filter(
            _country_detail_quality_filter()
        ).only(
            'name_common', 'cca3', 'flag_png', 'flag_emoji', 'status'
        ).order_by('name_common')

    if category != 'country':
        fc_filter = Q(is_public=True)
        if category != 'all':
            fc_filter &= Q(category=category)
        
        if search_query:
            fc_filter &= Q(name__icontains=search_query)

        flag_qs = FlagCollection.objects.filter(fc_filter).only(
            'name', 'flag_image', 'category', 'slug'
        ).order_by('name')

    return country_qs, flag_qs


def flag_detail(request, category, slug):
    """Detail page for a specific flag using category + slug URL."""
    # Added is_public=True so hidden flags return 404 even via direct URL
    flag = get_object_or_404(FlagCollection, slug=slug, is_public=True)
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

    from django.utils.translation import get_language
    current_lang = get_language() or 'en'

    # Zkusí vzít text pro aktuální jazyk, pokud není, vezme angličtinu
    localized_description = desc.get(current_lang) or desc.get('en', '')
    navigation_context = _build_flag_navigation_context(flag, request)
    
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


def flags_gallery(request):
    category = request.GET.get('category', 'all')
    search_query = request.GET.get('search') or request.GET.get('q') or ''
    search_query = search_query.strip()

    # Získáme QuerySety 
    country_qs, flag_qs = _collect_gallery_querysets(category, search_query)

    # Stáhneme validní státy 
    country_items = []
    for c in country_qs:
        link = reverse('country_detail', kwargs={'cca3': c.cca3}) if c.status != 'territory' else reverse('territory_detail', kwargs={'cca3': c.cca3})
        country_items.append({
            'name': c.name_common,
            'img': c.flag_png,
            'emoji': c.flag_emoji,
            'link': link,
            'badge': _('Country') if c.status == 'sovereign' else c.get_status_display(),
            'item_category': 'country' if c.status == 'sovereign' else c.status,
        })

    #Připravíme paginator pro tisíce zbytků v DB
    page_number = int(request.GET.get('page', 1))
    per_page = GALLERY_PER_PAGE
    
    # Výpočet: kolik států už jsme zobrazili vs. kolik vlajek z DB potřebujeme
    
    total_countries_count = len(country_items)
    
    start_index = (page_number - 1) * per_page
    end_index = start_index + per_page

    items_to_display = []

    if start_index < total_countries_count:
        # Jsme na stránce, kde se ještě zobrazují státy
        items_to_display.extend(country_items[start_index:end_index])
        
        remaining_slots = per_page - len(items_to_display)
        if remaining_slots > 0:
            # Vytáhneme prvních pár vlajek z databáze (SQL: LIMIT remaining_slots OFFSET 0)
            db_flags = flag_qs[:remaining_slots]
            for f in db_flags:
                items_to_display.append({
                    'name': f.name, 'img': f.flag_image, 'badge': f.get_category_display(),
                    'link': _build_flag_detail_link(
                        f,
                        source='gallery',
                        search_query=search_query,
                        page=page_number,
                        gallery_category=category,
                    ),
                    'item_category': f.category,
                })
    else:
        # Jsme na stránkách, kde už jsou jen vlajky (státy už skončily)
        db_offset = start_index - total_countries_count
        # SQL: LIMIT per_page OFFSET db_offset
        db_flags = flag_qs[db_offset : db_offset + per_page]
        for f in db_flags:
            items_to_display.append({
                'name': f.name, 'img': f.flag_image, 'badge': f.get_category_display(),
                'link': _build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    page=page_number,
                    gallery_category=category,
                ),
                'item_category': f.category,
            })

    # Manuální vytvoření Paginator objektu pro šablonu
    total_flags_count = flag_qs.count() # SQL COUNT() dotaz - super rychlý
    total_combined_items = total_countries_count + total_flags_count
    
    # Šabloně musíme předat "falešný" seznam s None, aby si Paginator myslel, že má vše, ale reálně nemá.
    # Nebo jednodušeji vytvoříme paginátor s vlastním počtem:
    class DummyPaginator(Paginator):
        def __init__(self, count, per_page):
            self._count = count
            super().__init__([], per_page)
        @property
        def count(self):
            return self._count
            
    paginator = DummyPaginator(total_combined_items, per_page)
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = items_to_display # Narveme tam jen těch 50 našich položek

    # --- Počítadla pro hlavičku a pilulky (Tyto zůstávají stejné) ---
    fc_counts = dict(FlagCollection.objects.filter(is_public=True).values_list('category').annotate(n=Count('id')))
    # Zjednodušené sčítání pro zrychlení
    pill_country_count = Country.objects.filter(status='sovereign').count() 
    pill_territory_count = Country.objects.filter(status='territory').count() + fc_counts.get('territory', 0)
    pill_historical_count = Country.objects.filter(status='historical').count() + fc_counts.get('historical', 0)
    total_flags_header = pill_country_count + pill_territory_count + pill_historical_count + fc_counts.get('state', 0) + fc_counts.get('city', 0) + fc_counts.get('region', 0) + fc_counts.get('international', 0)

    cat_counts = {
        'state': fc_counts.get('state', 0), 'city': fc_counts.get('city', 0),
        'region': fc_counts.get('region', 0), 'international': fc_counts.get('international', 0),
        'territory': pill_territory_count, 'historical': pill_historical_count, 'country': pill_country_count,
    }

    context = {
        'page_obj': page_obj,
        'selected_category': category,
        'search_query': search_query,
        'cat_counts': cat_counts,
        'total_flags': total_flags_header,
    }
    return render(request, 'flags_gallery.html', context)


def flags_search_api(request):
    """Global gallery search endpoint used by instant client-side search."""
    category = request.GET.get('category', 'all')
    search_query = (request.GET.get('q') or '').strip()

    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})

    max_items = 200
    items = []

    show_countries = category in ('all', 'country', 'territory', 'historical')
    if show_countries:
        statuses = ['sovereign', 'territory', 'historical']
        if category == 'country':
            statuses = ['sovereign']
        elif category == 'territory':
            statuses = ['territory']
        elif category == 'historical':
            statuses = ['historical']

        country_qs = Country.objects.filter(
            status__in=statuses,
            name_common__icontains=search_query,
        ).select_related('region').only(
            'name_common', 'name_official', 'cca2', 'cca3', 'capital', 'region',
            'area', 'population', 'currencies', 'languages',
            'flag_png', 'flag_svg', 'flag_emoji', 'status',
        )[:600]

        for c in country_qs:
            if c.status == 'territory':
                if not _is_territory_detail_eligible(c):
                    continue
                link = reverse('territory_detail', kwargs={'cca3': c.cca3})
            else:
                if not _is_country_detail_eligible(c):
                    continue
                link = reverse('country_detail', kwargs={'cca3': c.cca3})

            items.append({
                'name': c.name_common,
                'img': c.flag_png,
                'emoji': c.flag_emoji,
                'link': link,
            })
            if len(items) >= max_items:
                break

    if category != 'country' and len(items) < max_items:
        # Added is_public=True to search API
        flag_qs = FlagCollection.objects.filter(name__icontains=search_query, is_public=True).only('name', 'flag_image', 'category', 'slug')
        if category != 'all':
            flag_qs = flag_qs.filter(category=category)

        for f in flag_qs[:800]:
            items.append({
                'name': f.name,
                'img': f.flag_image,
                'link': _build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    gallery_category=category,
                ),
            })
            if len(items) >= max_items:
                break

    total = len(items)

    return JsonResponse({
        'items': items,
        'total': total,
        'truncated': total >= max_items,
    })


def countries_search_api(request):
    """AJAX search endpoint for countries section with instant search"""
    region_filter = request.GET.get('region', '')
    search_query = (request.GET.get('q') or '').strip()
    
    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})
    
    max_items = 200
    items = []
    
    countries_qs = Country.objects.filter(status='sovereign').filter(
        _country_detail_quality_filter()
    ).select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji', 'region__name', 'region__slug'
    ).order_by('name_common')

    if region_filter:
        countries_qs = countries_qs.filter(region__slug=region_filter)

    countries_qs = countries_qs.filter(_build_country_search_filter(search_query, 'name_common', 'capital'))
    for c in countries_qs[:max_items]:
        items.append({
            'name': c.name_common,
            'cca3': c.cca3,
            'link': reverse('country_detail', kwargs={'cca3': c.cca3}),
            'capital': c.capital or '',
            'img': c.flag_png,
            'emoji': c.flag_emoji,
            'region': c.region.name if c.region else '',
        })
    
    total = len(items)
    
    return JsonResponse({
        'items': items,
        'total': total,
        'truncated': total >= max_items,
    })


def territories_search_api(request):
    """AJAX search endpoint for territories page."""
    search_query = (request.GET.get('q') or '').strip()

    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})

    max_items = 200
    items = []

    territory_qs = Country.objects.filter(status='territory').filter(
        _country_detail_quality_filter()
    ).only('name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji').order_by('name_common')
    territory_qs = territory_qs.filter(_build_country_search_filter(search_query, 'name_common', 'capital'))

    for c in territory_qs[:max_items]:
        items.append({
            'name': c.name_common,
            'cca3': c.cca3,
            'link': reverse('territory_detail', kwargs={'cca3': c.cca3}),
            'capital': c.capital or '',
            'img': c.flag_png,
            'emoji': c.flag_emoji,
        })

    if len(items) < max_items:
        stripped_query = _strip_accents(search_query)
        fc_filter = Q(name__icontains=search_query)
        if stripped_query and stripped_query != search_query:
            fc_filter |= Q(name__icontains=stripped_query)

        extra_qs = FlagCollection.objects.filter(
            category='territory',
            is_public=True,
        ).filter(fc_filter).only('name', 'flag_image').order_by('name')

        for f in extra_qs[:max_items - len(items)]:
            items.append({
                'name': f.name,
                'img': f.flag_image,
                'link': _build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    gallery_category='territory',
                ),
            })

    total = len(items)
    return JsonResponse({
        'items': items,
        'total': total,
        'truncated': total >= max_items,
    })


def historical_search_api(request):
    """AJAX search endpoint for historical gallery page."""
    search_query = (request.GET.get('q') or '').strip()

    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})

    max_items = 200
    items = []

    country_qs = Country.objects.filter(status='historical').filter(
        _country_detail_quality_filter()
    ).only('name_common', 'cca3', 'flag_png', 'flag_emoji').order_by('name_common')
    country_qs = country_qs.filter(_build_country_search_filter(search_query, 'name_common'))

    for c in country_qs[:max_items]:
        items.append({
            'name': c.name_common,
            'link': reverse('country_detail', kwargs={'cca3': c.cca3}),
            'img': c.flag_png,
            'emoji': c.flag_emoji,
            'type': _('Former Country'),
        })

    if len(items) < max_items:
        stripped_query = _strip_accents(search_query)
        flag_filter = Q(name__icontains=search_query)
        if stripped_query and stripped_query != search_query:
            flag_filter |= Q(name__icontains=stripped_query)

        flag_qs = FlagCollection.objects.filter(
            category='historical',
            is_public=True,
        ).filter(flag_filter).only('name', 'flag_image').order_by('name')

        for f in flag_qs[:max_items - len(items)]:
            items.append({
                'name': f.name,
                'img': f.flag_image,
                'type': _('Historical Flag'),
                'link': _build_flag_detail_link(
                    f,
                    source='historical',
                    search_query=search_query,
                ),
            })

    total = len(items)
    return JsonResponse({
        'items': items,
        'total': total,
        'truncated': total >= max_items,
    })


def render_about(request):
    """About page"""
    return render(request, 'about.html')