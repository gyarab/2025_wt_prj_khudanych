"""
Pydantic schemas for django-ninja API serialization.
These define the structure and types of API responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from decimal import Decimal
from datetime import datetime


# ==================== NESTED / COMPONENT SCHEMAS ====================

class CoordinatesSchema(BaseModel):
    """Geographic coordinates (lat/lon)"""
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None


class RegionSchema(BaseModel):
    """Lightweight region schema"""
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True


class FlagCollectionListSchema(BaseModel):
    """Lightweight flag collection for lists"""
    id: int
    name: str
    slug: str
    category: str
    flag_image: str
    flag_emoji: Optional[str] = None

    class Config:
        from_attributes = True


class FlagCollectionDetailSchema(BaseModel):
    """Full flag collection schema"""
    id: int
    name: str
    name_cs: str = ""
    name_de: str = ""
    slug: str
    category: str
    description: Dict[str, Any] = {}
    flag_image: str
    population: Optional[int] = None
    area_km2: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    wikidata_id: Optional[str] = None
    is_verified: bool
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== COUNTRY SCHEMAS ====================

class CountryListSchema(BaseModel):
    """Lightweight schema for country list endpoints"""
    cca3: str
    cca2: str
    name_common: str
    capital: str
    region: str  # Just region name for list
    population: int
    area_km2: Optional[Decimal] = None
    flag_emoji: str
    flag_png: str
    status: str
    coordinates: CoordinatesSchema

    class Config:
        from_attributes = True


class CountryDetailSchema(BaseModel):
    """Full schema for country detail endpoints with nested flags"""
    cca3: str
    cca2: str
    name_common: str
    name_official: str
    name_cs: str = ""
    name_de: str = ""
    capital: str
    capital_cs: str = ""
    capital_de: str = ""
    region: Optional[RegionSchema] = None  # Nested region object
    subregion: str = ""
    population: int
    area_km2: Optional[Decimal] = None
    flag_emoji: str
    flag_png: str
    flag_svg: str
    coat_of_arms_png: str = ""
    coat_of_arms_svg: str = ""
    currencies: Dict[str, Any] = Field(default_factory=dict)
    languages: Dict[str, Any] = Field(default_factory=dict)
    timezones: List[str] = Field(default_factory=list)
    continents: List[str] = Field(default_factory=list)
    borders: List[str] = Field(default_factory=list)
    status: str
    independent: bool
    un_member: bool
    system_of_government: Optional[str] = None
    coordinates: CoordinatesSchema = Field(default_factory=CoordinatesSchema)
    
    # Nested flag collections (top flags related to this country)
    additional_flags: List[FlagCollectionDetailSchema] = Field(default_factory=list)
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CountrySearchSchema(BaseModel):
    """Lightweight schema for search results"""
    cca3: str
    cca2: str
    name_common: str
    flag_emoji: str
    flag_png: str
    capital: str
    region: str
    status: str

    class Config:
        from_attributes = True


# ==================== RESPONSE WRAPPERS ====================

class PaginatedCountryListSchema(BaseModel):
    """Paginated response wrapper for country list"""
    items: List[CountryListSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


class SearchItemSchema(BaseModel):
    """Search result item with localization support"""
    name: str
    localized_name: str
    img: str
    emoji: Optional[str] = None
    link: str
    cca3: Optional[str] = None
    capital: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SearchResponseSchema(BaseModel):
    """Search response wrapper"""
    items: List[SearchItemSchema]
    total: int
    truncated: bool = False


class CountryCreateUpdateSchema(BaseModel):
    """Schema for creating/updating countries (admin only)"""
    name_common: str
    name_official: str
    cca2: str
    cca3: str
    capital: str = ""
    region: Optional[int] = None
    subregion: str = ""
    population: int = 0
    area_km2: Optional[Decimal] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    flag_emoji: str = ""
    flag_png: str = ""
    flag_svg: str = ""
    currencies: Dict[str, Any] = Field(default_factory=dict)
    languages: Dict[str, Any] = Field(default_factory=dict)
    timezones: List[str] = Field(default_factory=list)
    borders: List[str] = Field(default_factory=list)
    status: str = "sovereign"
    independent: bool = True
    un_member: bool = False
