"""
Eligibility validation logic for country and territory detail pages.
"""

import logging

from ..models import Country
import flag_search_core


logger = logging.getLogger(__name__)


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


def has_complete_country_template_data(country: Country) -> bool:
    """Check whether a country has complete data required by detail templates."""
    if not country:
        return False

    has_required_identity = bool(country.name_common and country.name_official and country.cca2 and country.cca3)
    has_required_flag = bool(country.flag_emoji and (country.flag_svg or country.flag_png))
    has_required_geo = bool(country.capital and country.region and country.area_km2 is not None)
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


def is_country_detail_eligible(country: Country) -> bool:
    """Country detail pages are for sovereign/historical records with complete data."""
    return bool(country and country.status in ('sovereign', 'historical') and has_complete_country_template_data(country))


def is_territory_detail_eligible(country: Country) -> bool:
    """Territory detail pages are for territory records with complete data."""
    return bool(country and country.status == 'territory' and has_complete_country_template_data(country))


def get_territory_owner_country(territory: Country):
    """Resolve the sovereign owner country for a territory.
    
    First tries database relationship, then falls back to dictionary lookup
    and Rust-based text parsing for edge cases.
    """
    # Primary: Use database relationship
    if territory.owner and is_country_detail_eligible(territory.owner):
        return territory.owner
    
    # Fallback: Dictionary lookup O(1)
    owner_cca3 = TERRITORY_OWNER_BY_CCA3.get(territory.cca3)
    
    if not owner_cca3:
        # Last resort: Rust-based substring search
        text = f"{territory.name_common or ''} {territory.name_official or ''}"
        rust_owner_resolver = getattr(flag_search_core, 'identify_owner_cca3', None)
        if callable(rust_owner_resolver):
            owner_cca3 = rust_owner_resolver(text)
        else:
            logger.warning(
                "flag_search_core.identify_owner_cca3 is unavailable; "
                "skipping Rust owner resolution for territory %s",
                territory.cca3,
            )

    if owner_cca3:
        owner = Country.objects.filter(cca3=owner_cca3).first()
        if owner and is_country_detail_eligible(owner):
            return owner

    return None
