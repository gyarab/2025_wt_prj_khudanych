"""
AJAX/JSON search endpoints for instant client-side search.
"""

from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ..models import Country, FlagCollection
from .search_filters import (
    country_detail_quality_filter,
    build_country_search_filter,
    build_flag_name_search_filter,
)
from .pagination_helpers import build_flag_detail_link
from .eligibility import is_country_detail_eligible, is_territory_detail_eligible
from .text_utils import normalize_query


def flags_search_api(request):
    """Global gallery search endpoint used by instant client-side search."""
    category = request.GET.get('category', 'all')
    search_query = (request.GET.get('q') or '').strip()
    normalized_search_query = normalize_query(search_query)

    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})

    max_items = 200
    items = []

    show_countries = category in ('all', 'country', 'dependency', 'historical')
    if show_countries:
        statuses = ['sovereign', 'territory', 'historical']
        if category == 'country':
            statuses = ['sovereign']
        elif category == 'dependency':
            statuses = ['territory']
        elif category == 'historical':
            statuses = ['historical']

        country_qs = Country.objects.filter(
            status__in=statuses,
        ).filter(
            build_country_search_filter(normalized_search_query)
        ).select_related('region').only(
            'name_common', 'name_official', 'cca2', 'cca3', 'capital', 'region',
            'area_km2', 'population', 'currencies', 'languages',
            'flag_png', 'flag_svg', 'flag_emoji', 'status',
        )[:600]

        for c in country_qs:
            if c.status == 'territory':
                if not is_territory_detail_eligible(c):
                    continue
                link = reverse('territory_detail', kwargs={'cca3': c.cca3})
            else:
                if not is_country_detail_eligible(c):
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
        flag_qs = FlagCollection.objects.filter(is_public=True).filter(
            build_flag_name_search_filter(normalized_search_query)
        ).only('name', 'name_cs', 'name_de', 'flag_image', 'category', 'slug')
        if category != 'all':
            flag_qs = flag_qs.filter(category=category)

        for f in flag_qs[:800]:
            items.append({
                'name': f.name,
                'localized_name': f.localized_name,
                'img': f.flag_image,
                'link': build_flag_detail_link(
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
    normalized_search_query = normalize_query(search_query)
    
    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})
    
    max_items = 200
    items = []
    
    countries_qs = Country.objects.filter(status='sovereign').filter(
        country_detail_quality_filter()
    ).select_related('region').only(
        'name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji', 'region__name', 'region__slug'
    ).order_by('name_common')

    if region_filter:
        countries_qs = countries_qs.filter(region__slug=region_filter)

    countries_qs = countries_qs.filter(build_country_search_filter(normalized_search_query))
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
    normalized_search_query = normalize_query(search_query)

    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})

    max_items = 200
    items = []

    territory_qs = Country.objects.filter(status='territory').filter(
        country_detail_quality_filter()
    ).only('name_common', 'cca3', 'capital', 'flag_png', 'flag_emoji').order_by('name_common')
    territory_qs = territory_qs.filter(build_country_search_filter(normalized_search_query))

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
        extra_qs = FlagCollection.objects.filter(
            category='dependency',
            is_public=True,
        ).filter(build_flag_name_search_filter(normalized_search_query)).only('name', 'name_cs', 'name_de', 'flag_image').order_by('name')

        for f in extra_qs[:max_items - len(items)]:
            items.append({
                'name': f.name,
                'localized_name': f.localized_name,
                'img': f.flag_image,
                'link': build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    gallery_category='dependency',
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
    normalized_search_query = normalize_query(search_query)

    if len(search_query) < 2:
        return JsonResponse({'items': [], 'total': 0, 'truncated': False})

    max_items = 200
    items = []

    country_qs = Country.objects.filter(status='historical').filter(
        country_detail_quality_filter()
    ).only('name_common', 'cca3', 'flag_png', 'flag_emoji').order_by('name_common')
    country_qs = country_qs.filter(build_country_search_filter(normalized_search_query))

    for c in country_qs[:max_items]:
        items.append({
            'name': c.name_common,
            'link': reverse('country_detail', kwargs={'cca3': c.cca3}),
            'img': c.flag_png,
            'emoji': c.flag_emoji,
            'type': _('Former Country'),
        })

    if len(items) < max_items:
        flag_qs = FlagCollection.objects.filter(
            category='historical',
            is_public=True,
        ).filter(build_flag_name_search_filter(normalized_search_query)).only('name', 'name_cs', 'name_de', 'flag_image').order_by('name')

        for f in flag_qs[:max_items - len(items)]:
            items.append({
                'name': f.name,
                'localized_name': f.localized_name,
                'img': f.flag_image,
                'type': _('Historical Flag'),
                'link': build_flag_detail_link(
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
