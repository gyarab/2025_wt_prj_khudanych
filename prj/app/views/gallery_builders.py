"""
Gallery collection and rendering logic for flag galleries.
"""

from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ..models import Country, FlagCollection
from .search_filters import country_detail_quality_filter
from .pagination_helpers import build_flag_detail_link, GALLERY_PER_PAGE


def collect_gallery_querysets(category, search_query=''):
    """Collect appropriate QuerySets based on gallery category and search."""
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
            allowed_statuses = ['sovereign', 'territory', 'historical']

        country_filter = Q(status__in=allowed_statuses)

        if search_query:
            country_filter &= Q(name_common__icontains=search_query)

        country_qs = Country.objects.filter(country_filter).filter(
            country_detail_quality_filter()
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


def flags_gallery(request):
    """Main flags gallery with combined countries and FlagCollection items."""
    category = request.GET.get('category', 'all')
    search_query = request.GET.get('search') or request.GET.get('q') or ''
    search_query = search_query.strip()

    country_qs, flag_qs = collect_gallery_querysets(category, search_query)

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

    page_number = int(request.GET.get('page', 1))
    per_page = GALLERY_PER_PAGE
    
    total_countries_count = len(country_items)
    
    start_index = (page_number - 1) * per_page
    end_index = start_index + per_page

    items_to_display = []

    if start_index < total_countries_count:
        items_to_display.extend(country_items[start_index:end_index])
        
        remaining_slots = per_page - len(items_to_display)
        if remaining_slots > 0:
            db_flags = flag_qs[:remaining_slots]
            for f in db_flags:
                items_to_display.append({
                    'name': f.name,
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

    fc_counts = dict(FlagCollection.objects.filter(is_public=True).values_list('category').annotate(n=Count('id')))
    pill_country_count = Country.objects.filter(status='sovereign').count()
    pill_territory_count = Country.objects.filter(status='territory').count() + fc_counts.get('territory', 0)
    pill_historical_count = Country.objects.filter(status='historical').count() + fc_counts.get('historical', 0)
    total_flags_header = pill_country_count + pill_territory_count + pill_historical_count + fc_counts.get('state', 0) + fc_counts.get('city', 0) + fc_counts.get('region', 0) + fc_counts.get('international', 0)

    cat_counts = {
        'state': fc_counts.get('state', 0),
        'city': fc_counts.get('city', 0),
        'region': fc_counts.get('region', 0),
        'international': fc_counts.get('international', 0),
        'territory': pill_territory_count,
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
