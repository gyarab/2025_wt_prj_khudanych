# Just Enough Flags

[![Django](https://img.shields.io/badge/Django-5.x-0C4B33?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Data](https://img.shields.io/badge/Data-Wikidata%20%2B%20Wikimedia%20Commons-006699)](https://www.wikidata.org/)
[![License: Source-Available](https://img.shields.io/badge/License-Source--Available-red.svg)](LICENSE)

A modern Django web app for geography and vexillology.
It combines country metadata with a large flag catalog and searchable galleries across countries, territories, historical entities, and international organizations.

## Why This Project

- Large and diverse flag dataset with practical browsing views
- Real ETL workflow from Wikidata SPARQL
- Local seed pipeline for base country data
- Multilingual UI foundations (EN, CS, DE)
- Authentication-ready architecture (including Google provider via Allauth)

## System Visuals

| User Flow | Wireframes |
| :---: | :---: |
| ![User Flow](docs/assets/user-flow.jpg) | ![Wireframes](docs/assets/wireframes.jpg) |

![Entity-relationship diagram](docs/assets/FixedER.png)

## Tech Stack

- Backend: Python, Django
- Frontend: Django templates, Bootstrap 5, Bootstrap Icons, JavaScript
- Styling/Font: Poppins (Google Fonts)
- Database: PostgreSQL (project default in settings)
- Data ingestion: Wikidata SPARQL + custom management commands

## Quick Start

### 1. Clone

```bash
git clone https://github.com/gyarab/2025_wt_prj_khudanych.git
cd 2025_wt_prj_khudanych
```

### 2. Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r prj/requirements.txt
```

Optional dev dependencies:

```bash
pip install -r prj/requirements-dev.txt
```

### 4. Configure environment variables

Create `prj/.env` with at least:

```env
DJANGO_ENV=development
DJANGO_SECRET_KEY=replace_with_your_secret
DJANGO_DEBUG=1

DB_NAME=your_db
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=5432
```

### 5. Migrate and run

```bash
cd prj
python manage.py migrate
python manage.py runserver
```

Open: http://127.0.0.1:8000

## Data Pipeline (Current Commands)

```bash
cd prj

# Base countries from local countries.json (mledoze/countries source)
python manage.py setup_base_countries

# Fetch and upsert flags and metadata from Wikidata / Wikimedia Commons
python manage.py fetch_wikidata_flags --limit-per-category 3000

# Sync selected values and rebuild normalized search text
python manage.py sync_countries
python manage.py backfill_flag_search_names
```

## Data Source and Asset Provenance

- Primary flags/metadata pipeline: Wikidata + Wikimedia Commons file paths
- Base country seed: local `countries.json` sourced from `mledoze/countries`
- Additional country flag URLs for base seed: `flagcdn.com`

Important: third-party data and media are not re-licensed by the project license.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and compliance notes.

## License

This repository is publicly visible solely for educational, portfolio, and code-review purposes.
The source code is not open source and no license grant is provided beyond the permissions stated in [LICENSE](LICENSE).

Permitted use is limited to personal, non-commercial evaluation.
Without prior written permission from Serhii Khudanych, you may not use, copy, modify, merge, publish, distribute, sublicense, sell, deploy, host, or otherwise exploit this software, in whole or in part.

Serhii Khudanych retains all commercial rights, including monetization via advertising, subscriptions, freemium, licensing, and paid hosting.

- License text: [LICENSE](LICENSE)
- Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## Author

Serhii Khudanych  
Class: 2.F
