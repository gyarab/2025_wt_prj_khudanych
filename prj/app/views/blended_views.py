"""
Blended views combining Country and FlagCollection items.
Note: Territories have been migrated purely to the Country model, 
so only historical views remain truly 'blended'.
"""

from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Q

from ..models import Country, FlagCollection
from .search_filters import (
    country_detail_quality_filter,
    build_country_search_filter,
    build_flag_name_search_filter,
    get_country_search_rank,
)
from .text_utils import normalize_query
from .pagination_helpers import build_flag_detail_link, CountOnlyPaginator, COUNTRIES_PER_PAGE, GALLERY_PER_PAGE


def territories_list(request):
    """List territories and dependencies with DB-level pagination and instant search.
    Now queries purely from the Country model since the DB cleanup."""
    
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    normalized_search_query = normalize_query(search_query)

    # 1. Povolíme VŠECHNA teritoria a území bez ohledu na to, jak moc jsou vyplněná
    territory_qs = Country.objects.filter(
        Q(status='territory') | Q(independent=False) | Q(owner__isnull=False)
    ).select_related('region').order_by('name_common')

    if normalized_search_query:
        territory_qs = territory_qs.filter(build_country_search_filter(search_query))
        ranked_territories = []
        for country in territory_qs:
            rank = get_country_search_rank(country, search_query)
            if rank > 0:
                ranked_territories.append((rank, country))

        ranked_territories.sort(key=lambda item: (-item[0], item[1].name_common))
        territory_qs = [country for _, country in ranked_territories]

    # 2. Standardní Django stránkování (konec falešného CountOnlyPaginatoru)
    paginator = Paginator(territory_qs, COUNTRIES_PER_PAGE)
    page_obj = paginator.get_page(page_number)

    # 3. Dodání aliasů pro šablonu (aby šablona našla obrázky a URL adresy)
    for c in page_obj.object_list:
        c.link = reverse('territory_detail', kwargs={'cca3': c.cca3})
        c.type = _('Territory / Dependency')
        c.img = c.flag_png
        c.emoji = c.flag_emoji
        c.name = c.localized_name
        # Region a Capital si šablona automaticky vytáhne z objektu Country

    context = {
        'countries': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'search_api_url': reverse('territories_search_api'),
        'search_status': 'territory',
        'search_placeholder': _('Search territories...'),
        'page_title': _('Territories & Dependencies'),
        'compact_territory_cards': True,
    }
    return render(request, 'countries.html', context)


def historical_list(request):
    """List historical countries and flags with DB-level pagination and instant search."""
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    normalized_search_query = normalize_query(search_query)
    per_page = GALLERY_PER_PAGE

    historical_country_qs = Country.objects.filter(status='historical').filter(
        country_detail_quality_filter()
    ).only('name_common', 'name_cs', 'name_de', 'search_name', 'cca3', 'flag_png', 'flag_emoji').order_by('name_common')

    if normalized_search_query:
        historical_country_qs = historical_country_qs.filter(build_country_search_filter(search_query))
        ranked_historical_countries = []
        for country in historical_country_qs:
            rank = get_country_search_rank(country, search_query)
            if rank > 0:
                ranked_historical_countries.append((rank, country))

        ranked_historical_countries.sort(key=lambda item: (-item[0], item[1].name_common))
        historical_country_qs = [country for _, country in ranked_historical_countries]

    historical_flag_qs = FlagCollection.objects.filter(
        category='historical',
        is_public=True,
    ).only('name', 'name_cs', 'name_de', 'flag_image').order_by('name')

    if normalized_search_query:
        historical_flag_qs = historical_flag_qs.filter(build_flag_name_search_filter(search_query))

    total_countries_count = len(historical_country_qs) if isinstance(historical_country_qs, list) else historical_country_qs.count()
    total_flags_count = historical_flag_qs.count()
    total_combined = total_countries_count + total_flags_count

    start_index = (page_number - 1) * per_page
    end_index = start_index + per_page

    items_to_display = []

    if start_index < total_countries_count:
        for c in historical_country_qs[start_index:end_index]:
            items_to_display.append({
                'name': c.localized_name,
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
                    'localized_name': f.localized_name,
                    'img': f.flag_image,
                    'type': _('Historical Flag'),
                    'link': build_flag_detail_link(
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
                'localized_name': f.localized_name,
                'img': f.flag_image,
                'type': _('Historical Flag'),
                'link': build_flag_detail_link(
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