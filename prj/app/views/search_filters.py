"""
Complex QuerySet filter builders for database searches.
"""

from django.db.models import Q
from .text_utils import normalize_query


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
        Q(area_km2__isnull=False) &
        Q(population__gt=0) &
        Q(currencies__isnull=False) &
        ~Q(currencies={}) &
        Q(languages__isnull=False) &
        ~Q(languages={})
    )


def build_country_search_filter(search_query, *field_names):
    """Build DB filter for normalized indexed country search text."""
    if not search_query:
        return Q()

    normalized_query = normalize_query(search_query)
    if not normalized_query:
        return Q()

    return Q(search_name__icontains=normalized_query)


def build_flag_name_search_filter(search_query):
    """Normalized DB filter for flag names."""
    if not search_query:
        return Q()

    normalized_query = normalize_query(search_query)
    if not normalized_query:
        return Q()

    return Q(search_name__icontains=normalized_query)
