"""
Views package for the Just Enough Flags application.

This package refactors the monolithic views.py into modular, focused components:
- main_views: Primary route handlers (homepage, country/flag details, profiles)
- eligibility: Validation logic for detail page access
- text_utils: Rust-powered text processing
- search_filters: QuerySet filter builders
- pagination_helpers: Custom paginators and URL builders
- search_apis: AJAX/JSON search endpoints
- gallery_builders: Flag gallery collection logic
- blended_views: Combined Country + FlagCollection views
"""

# Import all views that need to be exposed to urls.py
from .main_views import (
    profile_view,
    profile_edit,
    render_homepage,
    countries_list,
    country_detail,
    territory_detail,
    flag_detail,
    render_about,
)

from .blended_views import (
    territories_list,
    historical_list,
)

from .gallery_builders import (
    flags_gallery,
)

from .search_apis import (
    flags_search_api,
    countries_search_api,
    territories_search_api,
    historical_search_api,
)

__all__ = [
    # Main views
    'profile_view',
    'profile_edit',
    'render_homepage',
    'countries_list',
    'country_detail',
    'territory_detail',
    'flag_detail',
    'render_about',
    # Blended views
    'territories_list',
    'historical_list',
    # Gallery
    'flags_gallery',
    # Search APIs
    'flags_search_api',
    'countries_search_api',
    'territories_search_api',
    'historical_search_api',
]
