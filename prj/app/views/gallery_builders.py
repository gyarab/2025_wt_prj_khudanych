"""
Gallery collection and rendering logic for flag galleries.
"""

from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ..models import Country, FlagCollection
from .search_filters import (
    country_detail_quality_filter,
    build_country_search_filter,
    build_flag_name_search_filter,
)
from .pagination_helpers import build_flag_detail_link, GALLERY_PER_PAGE
from .text_utils import normalize_query


def collect_gallery_querysets(category, search_query=''):
    """Collect appropriate QuerySets based on gallery category and search."""
    normalized_search_query = normalize_query(search_query)
    country_qs = Country.objects.none()
    flag_qs = FlagCollection.objects.none()

    show_countries = category in ('all', 'country', 'dependency', 'historical')
    
    if show_countries:
        if category == 'country':
            allowed_statuses = ['sovereign']
        elif category == 'dependency':
            allowed_statuses = ['territory']
        elif category == 'historical':
            allowed_statuses = ['historical']
        else:
            allowed_statuses = ['sovereign', 'territory', 'historical']

        country_filter = Q(status__in=allowed_statuses)

        if normalized_search_query:
            country_filter &= build_country_search_filter(normalized_search_query)

        country_qs = Country.objects.filter(country_filter).filter(
            country_detail_quality_filter()
        ).only(
            'name_common', 'cca3', 'flag_png', 'flag_emoji', 'status'
        ).order_by('name_common')

    if category != 'country':
        fc_filter = Q(is_public=True)
        if category != 'all':
            fc_filter &= Q(category=category)
        
        if normalized_search_query:
            fc_filter &= build_flag_name_search_filter(normalized_search_query)

        flag_qs = FlagCollection.objects.filter(fc_filter).only(
            'name', 'name_cs', 'name_de', 'flag_image', 'category', 'slug'
        ).order_by('name')

    return country_qs, flag_qs


def flags_gallery(request):
    """Main flags gallery with combined countries and FlagCollection items."""
    category = request.GET.get('category', 'all')
    search_query = request.GET.get('search') or request.GET.get('q') or ''
    search_query = search_query.strip()

    country_qs, flag_qs = collect_gallery_querysets(category, search_query)

    page_number = int(request.GET.get('page', 1))
    per_page = GALLERY_PER_PAGE
    
    # Use .count() instead of loading all items into memory
    total_countries_count = country_qs.count()
    
    start_index = (page_number - 1) * per_page
    end_index = start_index + per_page

    items_to_display = []

    # Use database-level slicing instead of loading everything into memory
    if start_index < total_countries_count:
        # Slice at database level, not in Python
        country_page = country_qs[start_index:end_index]
        
        for c in country_page:
            link = reverse('country_detail', kwargs={'cca3': c.cca3}) if c.status != 'territory' else reverse('territory_detail', kwargs={'cca3': c.cca3})
            items_to_display.append({
                'name': c.name_common,
                'img': c.flag_png,
                'emoji': c.flag_emoji,
                'link': link,
                'badge': _('Country') if c.status == 'sovereign' else c.get_status_display(),
                'item_category': 'country' if c.status == 'sovereign' else c.status,
            })
        
        remaining_slots = per_page - len(items_to_display)
        if remaining_slots > 0:
            db_flags = flag_qs[:remaining_slots]
            for f in db_flags:
                items_to_display.append({
                    'name': f.name,
                    'localized_name': f.localized_name,
                    'img': f.flag_image,
                    'badge': f.get_category_display(),
                    'link': build_flag_detail_link(
                        f,
                        source='gallery',
                        search_query=search_query,
                        page=page_number,
                        gallery_category=category,
                    ),
                    'item_category': f.category,
                })
    else:
        db_offset = start_index - total_countries_count
        db_flags = flag_qs[db_offset:db_offset + per_page]
        for f in db_flags:
            items_to_display.append({
                'name': f.name,
                'localized_name': f.localized_name,
                'img': f.flag_image,
                'badge': f.get_category_display(),
                'link': build_flag_detail_link(
                    f,
                    source='gallery',
                    search_query=search_query,
                    page=page_number,
                    gallery_category=category,
                ),
                'item_category': f.category,
            })

    total_flags_count = flag_qs.count()
    total_combined_items = total_countries_count + total_flags_count
    
    class DummyPaginator(Paginator):
        def __init__(self, count, per_page):
            self._count = count
            super().__init__([], per_page)
        
        @property
        def count(self):
            return self._count
            
    paginator = DummyPaginator(total_combined_items, per_page)
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = items_to_display

    public_flag_qs = FlagCollection.objects.filter(is_public=True)
    fc_counts = dict(public_flag_qs.values_list('category').annotate(n=Count('id')))

    gallery_country_base_qs = Country.objects.filter(country_detail_quality_filter())
    country_status_counts = dict(
        gallery_country_base_qs.values_list('status').annotate(n=Count('id'))
    )

    pill_country_count = country_status_counts.get('sovereign', 0)
    pill_territory_count = country_status_counts.get('territory', 0) + fc_counts.get('dependency', 0)
    pill_historical_count = country_status_counts.get('historical', 0) + fc_counts.get('historical', 0)

    gallery_country_total = gallery_country_base_qs.filter(
        status__in=['sovereign', 'territory', 'historical']
    ).count()
    total_flags_header = gallery_country_total + public_flag_qs.count()

    cat_counts = {
        'city': fc_counts.get('city', 0),
        'region': fc_counts.get('region', 0),
        'international': fc_counts.get('international', 0),
        'dependency': pill_territory_count,
        'historical': pill_historical_count,
        'country': pill_country_count,
    }

    context = {
        'page_obj': page_obj,
        'selected_category': category,
        'search_query': search_query,
        'cat_counts': cat_counts,
        'total_flags': total_flags_header,
    }
    return render(request, 'flags_gallery.html', context)
