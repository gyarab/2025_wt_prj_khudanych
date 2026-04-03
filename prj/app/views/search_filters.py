"""
Complex QuerySet filter builders for database searches.
"""

from django.db.models import Q
from .text_utils import strip_accents


def country_detail_quality_filter():
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
        Q(languages__isnull=False) &
        ~Q(languages={})
    )


def build_country_search_filter(search_query, *field_names):
    """Build DB filter for search text and its accent-stripped variant."""
    if not search_query:
        return Q()

    search_filter = Q()
    for field_name in field_names:
        search_filter |= Q(**{f"{field_name}__icontains": search_query})

    stripped_query = strip_accents(search_query)
    if stripped_query and stripped_query != search_query:
        for field_name in field_names:
            search_filter |= Q(**{f"{field_name}__icontains": stripped_query})

    return search_filter


def build_flag_name_search_filter(search_query):
    """Accent-insensitive DB filter for flag names."""
    if not search_query:
        return Q()

    search_filter = Q(name__icontains=search_query)
    stripped_query = strip_accents(search_query)
    if stripped_query and stripped_query != search_query:
        search_filter |= Q(name__icontains=stripped_query)
    return search_filter
