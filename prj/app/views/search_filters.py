"""
Complex QuerySet filter builders for database searches.
"""

from collections.abc import Iterable
from django.db.models import Q
from django.utils.translation import get_language
from .text_utils import normalize_query


COUNTRY_ALIAS_MAP = {
    'ceska republika': ('cesko', 'czechia', 'czech republic'),
    'czech republic': ('czechia', 'cesko'),
    'spolkova republika nemecko': ('nemecko', 'germany', 'deutschland'),
    'united states of america': ('united states', 'usa', 'spojene staty'),
    'great britain': ('united kingdom', 'uk', 'britain', 'velka britanie'),
}


def _get_active_country_language():
    return (get_language() or '').split('-')[0]


def _normalize_alias_targets(target_value):
    if isinstance(target_value, str):
        target_values = [target_value]
    elif isinstance(target_value, Iterable):
        target_values = [str(value) for value in target_value]
    else:
        target_values = [str(target_value)]

    normalized_values = []
    for value in target_values:
        normalized_value = normalize_query(value)
        if normalized_value:
            normalized_values.append(normalized_value)
    return normalized_values


def _get_country_search_fields():
    active_lang = _get_active_country_language()
    fields = ['name_common', 'search_name']
    if active_lang == 'cs':
        fields.append('name_cs')
    elif active_lang == 'de':
        fields.append('name_de')
    return fields


def resolve_country_search_terms(search_query):
    """Return normalized search terms with alias/synonym expansion."""
    normalized_query = normalize_query(search_query)
    if not normalized_query:
        return []

    expanded_terms = {normalized_query}
    for alias_key, alias_target in COUNTRY_ALIAS_MAP.items():
        normalized_key = normalize_query(alias_key)
        if not normalized_key:
            continue

        # Partial typing support: if query is contained in alias key, expand with alias targets.
        if normalized_query in normalized_key:
            expanded_terms.add(normalized_key)
            expanded_terms.update(_normalize_alias_targets(alias_target))

    # Deterministic order keeps query generation stable.
    return sorted(term for term in expanded_terms if term)


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
    """Build language-aware DB filter for country search."""
    search_terms = resolve_country_search_terms(search_query)
    if not search_terms:
        return Q()

    fields = _get_country_search_fields()
    query_filter = Q()
    for term in search_terms:
        for field_name in fields:
            query_filter |= Q(**{f'{field_name}__icontains': term})

    return query_filter


def get_country_search_rank(country, search_query):
    """Language-aware score for accent-insensitive country matching."""
    search_terms = resolve_country_search_terms(search_query)
    if not search_terms:
        return 0

    active_lang = _get_active_country_language()
    fields = _get_country_search_fields()

    field_values = {
        'name_common': normalize_query(getattr(country, 'name_common', '')),
        'search_name': normalize_query(getattr(country, 'search_name', '')),
        'name_cs': normalize_query(getattr(country, 'name_cs', '')),
        'name_de': normalize_query(getattr(country, 'name_de', '')),
    }

    base_weights = {
        'name_common': 90,
        'search_name': 80,
        'name_cs': 70,
        'name_de': 70,
    }

    if active_lang == 'cs':
        base_weights['name_cs'] += 30
    elif active_lang == 'de':
        base_weights['name_de'] += 30
    else:
        base_weights['name_common'] += 20

    best_score = 0
    for field_name in fields:
        normalized_value = field_values.get(field_name, '')
        if not normalized_value:
            continue

        for term in search_terms:
            if term not in normalized_value:
                continue

            score = base_weights[field_name]
            if normalized_value.startswith(term):
                score += 25
            if normalized_value == term:
                score += 50
            best_score = max(best_score, score)

    return best_score


def build_flag_name_search_filter(search_query):
    """Language-aware DB filter for flag names."""
    if not search_query:
        return Q()

    raw_query = str(search_query).strip()
    normalized_query = normalize_query(search_query)
    if not raw_query and not normalized_query:
        return Q()

    active_lang = _get_active_country_language()
    fields = ['name', 'search_name']
    if active_lang == 'cs':
        fields.append('name_cs')
    elif active_lang == 'de':
        fields.append('name_de')

    query_filter = Q()
    if normalized_query:
        query_filter |= Q(search_name__icontains=normalized_query)

    if raw_query:
        for field_name in fields:
            if field_name == 'search_name':
                continue
            query_filter |= Q(**{f'{field_name}__icontains': raw_query})

    return query_filter
