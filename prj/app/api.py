from typing import List, Optional
from ninja import NinjaAPI, Schema
from ninja.security import django_auth
from .models import Country

# Inicializace API podle vzoru
api = NinjaAPI(title="JEF API", description="REST API pro databázi vlajek Just Enough Flags.")

# ---------- 1. Schémata (Pydantic) ----------

class MessageSchema(Schema):
    message: str

class CountryOut(Schema):
    cca3: str
    cca2: str
    name_common: str
    name_official: str
    capital: str
    region: str
    subregion: str
    population: int
    area_km2: Optional[float] = None
    flag_svg: str
    flag_png: str
    is_independent: bool
    upvotes: int
    downvotes: int
    score: int  # Pydantic automaticky vytáhne hodnotu z naší @property v modelu

class CountryIn(Schema):
    cca3: str
    cca2: str
    name_common: str
    name_official: str
    capital: str = ""
    region: str
    subregion: str = ""
    population: int = 0
    area_km2: Optional[float] = None
    flag_svg: str
    flag_png: str
    is_independent: bool = True

# ---------- 2. Pomocné funkce (Helpers) ----------

def _apply_country_input(country: Country, payload: CountryIn) -> Country:
    # Vezme instanci modelu a naplní ji daty z API požadavku 
    country.cca3 = payload.cca3.upper()
    country.cca2 = payload.cca2.upper()
    country.name_common = payload.name_common
    country.name_official = payload.name_official
    country.capital = payload.capital
    country.region = payload.region
    country.subregion = payload.subregion
    country.population = payload.population
    country.area_km2 = payload.area_km2
    country.flag_svg = payload.flag_svg
    country.flag_png = payload.flag_png
    country.is_independent = payload.is_independent
    country.save()
    return country

# ---------- 3. API Endpoints ----------

# GET /api/countries -> Seznam všech států seřazených podle skóre
@api.get("/countries", response=List[CountryOut], tags=["countries"])
def list_countries(request):
    countries = list(Country.objects.all())
    return sorted(countries, key=lambda c: c.score, reverse=True)


# GET /api/countries/{cca3} -> Detail jednoho konkrétního státu
@api.get("/countries/{cca3}", response={200: CountryOut, 404: MessageSchema}, tags=["countries"])
def get_country(request, cca3: str):
    try:
        country = Country.objects.get(pk=cca3.upper())
        return 200, country
    except Country.DoesNotExist:
        return 404, {"message": f"Stát s kódem {cca3.upper()} nebyl nalezen."}


# POST /api/countries -> Založení nového státu (Vyžaduje přihlášení)
@api.post("/countries", response={201: CountryOut}, auth=django_auth, tags=["countries"])
def create_country(request, payload: CountryIn):
    country = _apply_country_input(Country(), payload)
    return 201, country


# PUT /api/countries/{cca3} -> Úprava stávajícího státu (Vyžaduje přihlášení)
@api.put("/countries/{cca3}", response={200: CountryOut, 404: MessageSchema}, auth=django_auth, tags=["countries"])
def update_country(request, cca3: str, payload: CountryIn):
    try:
        country = Country.objects.get(pk=cca3.upper())
    except Country.DoesNotExist:
        return 404, {"message": f"Stát s kódem {cca3.upper()} nebyl nalezen."}
    
    country = _apply_country_input(country, payload)
    return 200, country


# DELETE /api/countries/{cca3} -> Smazání státu (Vyžaduje přihlášení)
@api.delete("/countries/{cca3}", response={204: None, 404: MessageSchema}, auth=django_auth, tags=["countries"])
def delete_country(request, cca3: str):
    try:
        country = Country.objects.get(pk=cca3.upper())
        country.delete()
        return 204, None
    except Country.DoesNotExist:
        return 404, {"message": f"Stát s kódem {cca3.upper()} nebyl nalezen."}