"""
Custom paginators and URL context builders.
"""

from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from ..models import FlagCollection


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


def with_query_params(url, params):
    """Append query params to URL while skipping empty values."""
    clean_params = {k: v for k, v in params.items() if v not in (None, '')}
    if not clean_params:
        return url
    return f"{url}?{urlencode(clean_params)}"


def build_flag_detail_link(flag, source='', search_query='', page=None, gallery_category=''):
    """Create detail URL with optional source context used for prev/next navigation."""
    base_url = flag.get_smart_url()
    return with_query_params(base_url, {
        'src': source,
        'q': search_query,
        'page': page,
        'gallery_category': gallery_category,
    })


def build_flag_navigation_context(flag, request):
    """Build contextual previous/next links for flag detail pages."""
    from .search_filters import build_flag_name_search_filter
    
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
            qs = qs.filter(build_flag_name_search_filter(search_query))
    elif src == 'gallery':
        if gallery_category and gallery_category != 'all':
            qs = qs.filter(category=gallery_category)
        if search_query:
            qs = qs.filter(build_flag_name_search_filter(search_query))
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

    prev_flag_url = with_query_params(
        reverse('flag_detail', kwargs={'category': prev_flag.category, 'slug': prev_flag.slug}),
        nav_params,
    ) if prev_flag else None

    next_flag_url = with_query_params(
        reverse('flag_detail', kwargs={'category': next_flag.category, 'slug': next_flag.slug}),
        nav_params,
    ) if next_flag else None

    back_url = None
    if src == 'gallery':
        back_url = with_query_params(reverse('flags_gallery'), {
            'category': gallery_category or 'all',
            'q': search_query,
            'page': page,
        })
    elif src == 'historical':
        back_url = with_query_params(reverse('historical'), {
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


def normalize_and_paginate(items_list, request, per_page=GALLERY_PER_PAGE):
    """Shared helper for search, normalization and pagination across views."""
    search_query = request.GET.get('search') or request.GET.get('q') or ''
    if search_query:
        search_query = search_query.strip()

    paginator = Paginator(items_list, per_page)
    page = paginator.get_page(request.GET.get('page'))
    return page, search_query
