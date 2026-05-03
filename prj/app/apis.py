"""
Django-Ninja REST API for Countries and related models.
Handles all API endpoints: list, detail, search, create, update, delete.
"""

from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from ninja import NinjaAPI, Query
from ninja.errors import HttpError

from .models import Country, Region, FlagCollection
from .schemas import (
    CountryListSchema,
    CountryDetailSchema,
    PaginatedCountryListSchema,
    SearchResponseSchema,
    CountryCreateUpdateSchema,
    FlagCollectionDetailSchema,
)
from .views.search_filters import (
    build_country_search_filter,
    get_country_search_rank,
)
from .views.eligibility import is_country_detail_eligible, is_territory_detail_eligible


def _serialize_coordinates(country: Country) -> dict:
    return {
        "latitude": country.latitude,
        "longitude": country.longitude,
    }


def _serialize_region(country: Country) -> Optional[dict]:
    if not country.region:
        return None
    return {
        "id": country.region.id,
        "name": country.region.name,
        "slug": country.region.slug,
    }


def _serialize_country_list_item(country: Country) -> CountryListSchema:
    payload = {
        "cca3": country.cca3,
        "cca2": country.cca2,
        "name_common": country.name_common,
        "capital": country.capital or "",
        "region": country.region.name if country.region else "",
        "population": country.population,
        "area_km2": country.area_km2,
        "flag_emoji": country.flag_emoji,
        "flag_png": country.flag_png,
        "status": country.status,
        "coordinates": _serialize_coordinates(country),
    }
    return CountryListSchema.model_validate(payload)


def _serialize_country_detail(country: Country, flags: List[FlagCollection]) -> CountryDetailSchema:
    flags_payload = [
        FlagCollectionDetailSchema.model_validate(flag).model_dump()
        for flag in flags
    ]
    payload = {
        "cca3": country.cca3,
        "cca2": country.cca2,
        "name_common": country.name_common,
        "name_official": country.name_official,
        "name_cs": country.name_cs,
        "name_de": country.name_de,
        "capital": country.capital or "",
        "capital_cs": country.capital_cs,
        "capital_de": country.capital_de,
        "region": _serialize_region(country),
        "subregion": country.subregion or "",
        "population": country.population,
        "area_km2": country.area_km2,
        "flag_emoji": country.flag_emoji,
        "flag_png": country.flag_png,
        "flag_svg": country.flag_svg,
        "coat_of_arms_png": country.coat_of_arms_png,
        "coat_of_arms_svg": country.coat_of_arms_svg,
        "currencies": country.currencies or {},
        "languages": country.languages or {},
        "timezones": country.timezones or [],
        "continents": country.continents or [],
        "borders": country.borders or [],
        "status": country.status,
        "independent": country.independent,
        "un_member": country.un_member,
        "system_of_government": country.system_of_government,
        "coordinates": _serialize_coordinates(country),
        "additional_flags": flags_payload,
        "created_at": country.created_at,
        "updated_at": country.updated_at,
    }
    return CountryDetailSchema.model_validate(payload)


# Initialize the API router
api = NinjaAPI(
    title="Just Enough Flags API",
    description="REST API for accessing country and flag data",
    version="1.0.0",
    urls_namespace="api"
)


# ==================== AUTHENTICATION HELPERS ====================

def is_admin(request: HttpRequest) -> bool:
    """Check if user is admin"""
    return request.user and request.user.is_staff


def require_admin(request: HttpRequest) -> None:
    """Raise 403 if user is not admin"""
    if not is_admin(request):
        raise HttpError(403, "Admin access required")


# ==================== COUNTRY ENDPOINTS ====================

@api.get(
    '/countries/',
    response=PaginatedCountryListSchema,
    tags=['Countries'],
    summary='List all countries',
    description='Get paginated list of countries with optional filtering by status and region'
)
def list_countries(
    request: HttpRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    region: Optional[int] = Query(None),
):
    """
    List countries with pagination and filters.
    
    Query parameters:
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 200)
    - status: Filter by status ('sovereign', 'territory', 'historical')
    - region: Filter by region ID
    """
    # Start with all countries
    qs = Country.objects.select_related('region').prefetch_related('additional_flags')
    
    # Apply filters
    if status:
        qs = qs.filter(status=status)
    
    if region:
        qs = qs.filter(region_id=region)
    
    # Apply eligibility filters
    countries = [c for c in qs if is_country_detail_eligible(c) or is_territory_detail_eligible(c)]
    
    # Paginate
    paginator = Paginator(countries, page_size)
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    # Serialize
    items = [_serialize_country_list_item(c) for c in page_obj.object_list]
    
    return PaginatedCountryListSchema(
        items=items,
        total=paginator.count,
        page=page_obj.number,
        page_size=page_size,
        total_pages=paginator.num_pages,
    )


@api.get(
    '/countries/search/',
    response=SearchResponseSchema,
    tags=['Countries'],
    summary='Search countries',
    description='Search for countries by name with instant results'
)
def search_countries(
    request: HttpRequest,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    region: Optional[int] = Query(None),
):
    """
    Search countries by name.
    
    Query parameters:
    - q: Search query (required, min 1 char)
    - limit: Max results to return (default 50, max 200)
    - status: Filter by status ('sovereign', 'territory', 'historical')
    - region: Filter by region ID
    """
    if len(q) < 1:
        return SearchResponseSchema(items=[], total=0, truncated=False)
    
    # Use existing search filter logic
    qs = Country.objects.filter(
        build_country_search_filter(q)
    ).select_related('region').only(
        'name_common', 'name_cs', 'name_de', 'cca3', 'cca2',
        'capital', 'region', 'flag_emoji', 'flag_png', 'status'
    )
    
    # Apply status filter if specified
    if status:
        qs = qs.filter(status=status)
    
    # Apply region filter if specified
    if region:
        qs = qs.filter(region_id=region)
    
    # Apply eligibility filters
    results = [
        c for c in qs 
        if (is_country_detail_eligible(c) or is_territory_detail_eligible(c))
    ]
    
    # Rank by relevance
    ranked = sorted(
        results,
        key=lambda c: get_country_search_rank(c, q),
        reverse=True
    )[:limit * 2]  # Get extra to account for slicing
    
    truncated = len(results) > limit
    
    # Serialize with enhanced format
    items = []
    for country in ranked[:limit]:
        # Get the correct URL based on status
        if country.status == 'territory':
            link = reverse('territory_detail', kwargs={'cca3': country.cca3})
        else:
            link = reverse('country_detail', kwargs={'cca3': country.cca3})
        
        items.append({
            'name': country.name_common,
            'localized_name': country.localized_name,
            'img': country.flag_png,
            'emoji': country.flag_emoji,
            'link': link,
            'cca3': country.cca3,
            'capital': country.capital or '',
            'region': country.region.name if country.region else '',
            'latitude': country.latitude,
            'longitude': country.longitude,
        })
    
    return SearchResponseSchema(
        items=items,
        total=len(results),
        truncated=truncated,
    )


@api.get(
    '/countries/{cca3}/',
    response=CountryDetailSchema,
    tags=['Countries'],
    summary='Get country details',
    description='Get full details for a specific country by ISO Alpha-3 code'
)
def get_country_detail(request: HttpRequest, cca3: str):
    """
    Get full country details including related flags.
    
    Path parameters:
    - cca3: ISO Alpha-3 country code (e.g., 'USA', 'GBR')
    """
    country = get_object_or_404(Country, cca3=cca3.upper())
    
    # Verify eligibility
    if not (is_country_detail_eligible(country) or is_territory_detail_eligible(country)):
        raise HttpError(404, "Country not found or not eligible")
    
    # Fetch related flags (top 10)
    flags = country.additional_flags.filter(is_public=True).order_by('-is_verified', '-created_at')[:10]
    
    # Add nested flags to serialization
    return _serialize_country_detail(country, list(flags))


# ==================== ADMIN ENDPOINTS (Protected) ====================

@api.post(
    '/countries/',
    response=CountryDetailSchema,
    tags=['Countries (Admin)'],
    summary='Create country',
    description='Create a new country (admin only)'
)
def create_country(request: HttpRequest, payload: CountryCreateUpdateSchema):
    """
    Create a new country.
    
    Requires admin authentication.
    """
    require_admin(request)
    
    # Validate unique fields
    if Country.objects.filter(cca3=payload.cca3).exists():
        raise HttpError(400, f"Country with cca3 '{payload.cca3}' already exists")
    if Country.objects.filter(cca2=payload.cca2).exists():
        raise HttpError(400, f"Country with cca2 '{payload.cca2}' already exists")
    
    # Get region if specified
    region = None
    if payload.region:
        region = get_object_or_404(Region, id=payload.region)
    
    # Create country
    country = Country.objects.create(
        name_common=payload.name_common,
        name_official=payload.name_official,
        cca2=payload.cca2,
        cca3=payload.cca3,
        capital=payload.capital,
        region=region,
        subregion=payload.subregion,
        population=payload.population,
        area_km2=payload.area_km2,
        latitude=payload.latitude,
        longitude=payload.longitude,
        flag_emoji=payload.flag_emoji,
        flag_png=payload.flag_png,
        flag_svg=payload.flag_svg,
        currencies=payload.currencies,
        languages=payload.languages,
        timezones=payload.timezones,
        borders=payload.borders,
        status=payload.status,
        independent=payload.independent,
        un_member=payload.un_member,
    )
    
    return _serialize_country_detail(country, [])


@api.put(
    '/countries/{cca3}/',
    response=CountryDetailSchema,
    tags=['Countries (Admin)'],
    summary='Update country',
    description='Update an existing country (admin only)'
)
def update_country(request: HttpRequest, cca3: str, payload: CountryCreateUpdateSchema):
    """
    Update a country (partial update).
    
    Requires admin authentication.
    """
    require_admin(request)
    
    country = get_object_or_404(Country, cca3=cca3.upper())
    
    # Update fields
    country.name_common = payload.name_common
    country.name_official = payload.name_official
    country.capital = payload.capital
    country.subregion = payload.subregion
    country.population = payload.population
    country.area_km2 = payload.area_km2
    country.latitude = payload.latitude
    country.longitude = payload.longitude
    country.flag_emoji = payload.flag_emoji
    country.flag_png = payload.flag_png
    country.flag_svg = payload.flag_svg
    country.currencies = payload.currencies
    country.languages = payload.languages
    country.timezones = payload.timezones
    country.borders = payload.borders
    country.status = payload.status
    country.independent = payload.independent
    country.un_member = payload.un_member
    
    if payload.region:
        country.region = get_object_or_404(Region, id=payload.region)
    
    country.save()
    
    return _serialize_country_detail(country, [])


@api.delete(
    '/countries/{cca3}/',
    tags=['Countries (Admin)'],
    summary='Delete country',
    description='Delete a country (admin only)'
)
def delete_country(request: HttpRequest, cca3: str):
    """
    Delete a country.
    
    Requires admin authentication.
    """
    require_admin(request)
    
    country = get_object_or_404(Country, cca3=cca3.upper())
    country.delete()
    
    return {"success": True, "message": f"Country {cca3} deleted"}


# ==================== REGION ENDPOINTS ====================

@api.get(
    '/regions/',
    tags=['Regions'],
    summary='List all regions',
    description='Get all geographic regions'
)
def list_regions(request: HttpRequest):
    """List all regions"""
    regions = Region.objects.all().order_by('name')
    return [
        {
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
        }
        for r in regions
    ]


@api.get(
    '/regions/{region_id}/countries/',
    response=PaginatedCountryListSchema,
    tags=['Regions'],
    summary='List countries in region',
    description='Get all countries in a specific region'
)
def list_region_countries(
    request: HttpRequest,
    region_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    List countries in a specific region.
    
    Path parameters:
    - region_id: Region ID
    """
    region = get_object_or_404(Region, id=region_id)
    
    qs = Country.objects.filter(region=region).select_related('region')
    countries = [c for c in qs if is_country_detail_eligible(c) or is_territory_detail_eligible(c)]
    
    # Paginate
    paginator = Paginator(countries, page_size)
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    items = [_serialize_country_list_item(c) for c in page_obj.object_list]
    
    return PaginatedCountryListSchema(
        items=items,
        total=paginator.count,
        page=page_obj.number,
        page_size=page_size,
        total_pages=paginator.num_pages,
    )
