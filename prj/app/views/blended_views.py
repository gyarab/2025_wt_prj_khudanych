"""
Blended views combining Country and FlagCollection items (territories and historical).
"""

from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ..models import Country, FlagCollection
from .search_filters import country_detail_quality_filter, build_country_search_filter
from .text_utils import normalize_query
from .pagination_helpers import build_flag_detail_link, CountOnlyPaginator, COUNTRIES_PER_PAGE, GALLERY_PER_PAGE


def territories_list(request):
    """List territories and dependencies with DB-level pagination and instant search."""
    page_number = int(request.GET.get('page', 1))
    search_query = (request.GET.get('q') or request.GET.get('search') or '').strip()
    normalized_search_query = normalize_query(search_query)
    per_page = COUNTRIES_PER_PAGE

    territory_qs = Country.objects.filter(status='territory').filter(
        country_detail_quality_filter()
    ).select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji', 'region__name',
    ).order_by('name_common')

    if normalized_search_query:
        territory_qs = territory_qs.filter(build_country_search_filter(normalized_search_query))

    extra_territories_qs = FlagCollection.objects.filter(
        category='dependency',
        is_public=True,
    ).only('name', 'name_cs', 'name_de', 'flag_image').order_by('name')
    if normalized_search_query:
        extra_territories_qs = extra_territories_qs.filter(build_country_search_filter(normalized_search_query))

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
                    'localized_name': f.localized_name,
                    'img': f.flag_image,
                    'type': _('Territory / Dependency'),
                    'link': build_flag_detail_link(
                        f,
                        source='gallery',
                        search_query=search_query,
                        page=page_number,
                        gallery_category='dependency',
                    ),
                })
    else:
        db_offset = start_index - total_territories_count
        for f in extra_territories_qs[db_offset:db_offset + per_page]:
            items_to_display.append({
                'name': f.name,
                'localized_name': f.localized_name,
                'img': f.flag_image,
                'type': _('Territory / Dependency'),
                'link': build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    page=page_number,
                    gallery_category='dependency',
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
    normalized_search_query = normalize_query(search_query)
    per_page = GALLERY_PER_PAGE

    historical_country_qs = Country.objects.filter(status='historical').filter(
        country_detail_quality_filter()
    ).only('name_common', 'cca3', 'flag_png', 'flag_emoji').order_by('name_common')

    if normalized_search_query:
        historical_country_qs = historical_country_qs.filter(build_country_search_filter(normalized_search_query))

    historical_flag_qs = FlagCollection.objects.filter(
        category='historical',
        is_public=True,
    ).only('name', 'name_cs', 'name_de', 'flag_image').order_by('name')

    if normalized_search_query:
        historical_flag_qs = historical_flag_qs.filter(build_country_search_filter(normalized_search_query))

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
