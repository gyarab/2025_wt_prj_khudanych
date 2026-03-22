import unicodedata
from urllib.parse import quote
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.urls import reverse
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
    """Resolve the sovereign owner country for a territory."""
    owner_cca3 = TERRITORY_OWNER_BY_CCA3.get(territory.cca3)
    if owner_cca3:
        owner = Country.objects.filter(cca3=owner_cca3).first()
        if owner and _is_country_detail_eligible(owner):
            return owner

    owner_keywords = {
        'french': 'FRA',
        'british': 'GBR',
        'dutch': 'NLD',
        'netherlands': 'NLD',
        'american': 'USA',
        'united states': 'USA',
        'danish': 'DNK',
        'norwegian': 'NOR',
        'australian': 'AUS',
        'new zealand': 'NZL',
        'chinese': 'CHN',
        'hong kong': 'CHN',
        'macao': 'CHN',
        'macau': 'CHN',
    }
    text = f"{territory.name_common or ''} {territory.name_official or ''}".lower()
    for token, cca3 in owner_keywords.items():
        if token in text:
            owner = Country.objects.filter(cca3=cca3).first()
            if owner and _is_country_detail_eligible(owner):
                return owner

    return None


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
        if not _is_country_detail_eligible(c):
            continue
        items.append({
            'name': c.name_common,
            'cca3': c.cca3,
            'link': reverse('country_detail', kwargs={'cca3': c.cca3}),
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
    # Added is_public=True filter
    extra_territories = FlagCollection.objects.filter(category='territory', is_public=True).only('name', 'flag_image')

    items = []
    for c in countries:
        if not _is_territory_detail_eligible(c):
            continue
        items.append({
            'name': c.name_common, 'cca3': c.cca3,
            'link': reverse('territory_detail', kwargs={'cca3': c.cca3}),
            'img': c.flag_png,
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
        'compact_territory_cards': True,
    }
    return render(request, 'countries.html', context)


def historical_list(request):
    """List historical flags and former countries"""
    hist_countries = Country.objects.filter(status='historical').only('name_common', 'cca3', 'flag_png', 'flag_emoji')
    # Added is_public=True filter
    hist_flags = FlagCollection.objects.filter(category='historical', is_public=True).only('name', 'flag_image')

    items = []
    for c in hist_countries:
        if not _is_country_detail_eligible(c):
            continue
        items.append({'name': c.name_common, 'img': c.flag_png, 'emoji': c.flag_emoji,
                      'link': reverse('country_detail', kwargs={'cca3': c.cca3}), 'type': 'Former Country'})
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


def _collect_gallery_items(category):
    """Build gallery items for flags page and API search."""
    items = []

    show_countries = category in ('all', 'country', 'territory', 'historical')
    if show_countries:
        country_filter = Q()
        if category == 'country':
            country_filter = Q(status='sovereign')
        elif category == 'territory':
            country_filter = Q(status='territory')
        elif category == 'historical':
            country_filter = Q(status='historical')

        qs = Country.objects.filter(country_filter).only('name_common', 'cca3', 'flag_png', 'flag_emoji', 'status')
        for c in qs:
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
                'badge': 'Country' if c.status == 'sovereign' else c.get_status_display(),
                'item_category': 'country' if c.status == 'sovereign' else c.status,
            })

    if category != 'country':
        # Added is_public=True filter here!
        qs = FlagCollection.objects.filter(is_public=True).only('name', 'flag_image', 'category', 'slug')
        if category != 'all':
            qs = qs.filter(category=category)
        for f in qs:
            items.append({
                'name': f.name,
                'img': f.flag_image,
                'badge': f.get_category_display(),
                'link': reverse('flag_detail', kwargs={'category': f.category, 'slug': f.slug}),
                'item_category': f.category,
            })

    return items


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

    if flag.country:
        if area_km2 is None and flag.country.area is not None:
            area_km2 = float(flag.country.area)
        if population is None and flag.country.population:
            population = int(flag.country.population)
        if latitude is None and flag.country.latitude is not None:
            latitude = float(flag.country.latitude)
        if longitude is None and flag.country.longitude is not None:
            longitude = float(flag.country.longitude)

    label_en = desc.get('label_en', '') if isinstance(desc.get('label_en', ''), str) else ''
    wiki_label = label_en.strip() or flag.name
    wiki_url = None
    if wiki_label and not (wiki_label.startswith('Q') and wiki_label[1:].isdigit()):
        wiki_url = f"https://en.wikipedia.org/wiki/{quote(wiki_label.replace(' ', '_'))}"
    
    context = {
        'flag': flag,
        'native_names': native_names,
        'wikidata_type_list': wikidata_type_list,
        'population': population,
        'area_km2': area_km2,
        'latitude': latitude,
        'longitude': longitude,
        'wiki_url': wiki_url,
    }
    return render(request, 'flag_detail.html', context)


def flags_gallery(request):
    """Gallery view with pagination, search, and category filter"""
    category = request.GET.get('category', 'all')

    # Added is_public=True to counts so category pills show correct numbers
    fc_counts = dict(FlagCollection.objects.filter(is_public=True).values_list('category').annotate(n=Count('id')))

    eligible_country_count = sum(1 for c in Country.objects.filter(status='sovereign') if _is_country_detail_eligible(c))
    eligible_territory_count = sum(1 for c in Country.objects.filter(status='territory') if _is_territory_detail_eligible(c))
    eligible_historical_count = sum(1 for c in Country.objects.filter(status='historical') if _is_country_detail_eligible(c))

    pill_country_count = eligible_country_count
    pill_territory_count = eligible_territory_count + fc_counts.get('territory', 0)
    pill_historical_count = eligible_historical_count + fc_counts.get('historical', 0)
    total_flags = pill_country_count + pill_territory_count + pill_historical_count + fc_counts.get('state', 0) + fc_counts.get('city', 0) + fc_counts.get('region', 0) + fc_counts.get('international', 0)

    cat_counts = {
        'state': fc_counts.get('state', 0),
        'city': fc_counts.get('city', 0),
        'region': fc_counts.get('region', 0),
        'international': fc_counts.get('international', 0),
        'territory': pill_territory_count,
        'historical': pill_historical_count,
        'country': pill_country_count,
    }

    items = _collect_gallery_items(category)

    page, search_query = _normalize_and_paginate(items, request)

    context = {
        'page_obj': page,
        'selected_category': category,
        'search_query': search_query,
        'cat_counts': cat_counts,
        'total_flags': total_flags,
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
                'link': reverse('flag_detail', kwargs={'category': f.category, 'slug': f.slug}),
            })
            if len(items) >= max_items:
                break

    total = len(items)

    return JsonResponse({
        'items': items,
        'total': total,
        'truncated': total >= max_items,
    })


def render_about(request):
    """About page"""
    return render(request, 'about.html')