"""Test admin-protected django-ninja API endpoints.

Usage:
  python3 scripts/test_admin_api.py
"""

import json
import os
import random
import string
import sys
from pathlib import Path

import django

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "prj.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from app.models import Country


def get_unique_codes():
    for _ in range(1000):
        cca3 = "".join(random.choices(string.ascii_uppercase, k=3))
        cca2 = "".join(random.choices(string.ascii_uppercase, k=2))
        if not Country.objects.filter(cca3=cca3).exists() and not Country.objects.filter(cca2=cca2).exists():
            return cca2, cca3
    raise RuntimeError("Unable to generate unique country codes")


def ensure_staff_user(username: str, password: str):
    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(username=username)
    user.set_password(password)
    if not user.is_staff:
        user.is_staff = True
    if not user.is_superuser:
        user.is_superuser = True
    if not user.is_active:
        user.is_active = True
    user.save()
    return user


def main():
    username = "api_admin_test"
    password = "admin12345"

    ensure_staff_user(username, password)

    client = Client()
    logged_in = client.login(username=username, password=password)
    if not logged_in:
        raise RuntimeError("Login failed. Check username/password.")

    cca2, cca3 = get_unique_codes()

    create_payload = {
        "name_common": "Testland",
        "name_official": "The Testland Republic",
        "cca2": cca2,
        "cca3": cca3,
        "capital": "Test City",
        "region": None,
        "subregion": "",
        "population": 123456,
        "area_km2": 7890.0,
        "latitude": 10.1234567,
        "longitude": 20.1234567,
        "flag_emoji": "",
        "flag_png": "https://example.com/flag.png",
        "flag_svg": "https://example.com/flag.svg",
        "currencies": {"TST": {"name": {"en": "Test Dollar"}, "symbol": "T$"}},
        "languages": {"tst": {"en": "Testish"}},
        "timezones": ["UTC"],
        "borders": [],
        "status": "sovereign",
        "independent": True,
        "un_member": False,
    }

    print("POST /api/countries/")
    create_response = client.post(
        "/api/countries/",
        data=json.dumps(create_payload),
        content_type="application/json",
    )
    print(f"Status: {create_response.status_code}")
    try:
        print(json.dumps(create_response.json(), indent=2)[:2000])
    except Exception:
        print(create_response.content[:2000])

    if create_response.status_code >= 400:
        raise RuntimeError("Create failed. See response above.")

    update_payload = dict(create_payload)
    update_payload["capital"] = "Updated Test City"
    update_payload["population"] = 222222

    print("\nPUT /api/countries/{cca3}/")
    update_response = client.put(
        f"/api/countries/{cca3}/",
        data=json.dumps(update_payload),
        content_type="application/json",
    )
    print(f"Status: {update_response.status_code}")
    try:
        print(json.dumps(update_response.json(), indent=2)[:2000])
    except Exception:
        print(update_response.content[:2000])

    if update_response.status_code >= 400:
        raise RuntimeError("Update failed. See response above.")

    print("\nDone. POST and PUT succeeded.")


if __name__ == "__main__":
    main()
