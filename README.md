# 🌍 Just Enough Flags

A database-driven geography and flags web application built with Django. Browse **4,600+ flags** from countries, historical states, international organizations, territories, cities and regions — all sourced live from [Wikidata](https://www.wikidata.org/).

---

## ✨ Features

| Feature | Details |
|---|---|
| 🏳️ **Flag gallery** | 4,600+ flags with click-to-zoom lightbox |
| 🌐 **Countries** | 258 countries with real population, capital, area, borders |
| 📜 **Historical flags** | Nazi Germany, Ottoman Empire, Soviet Union, Byzantine Empire and 880+ more |
| 🤝 **International orgs** | EU, NATO, UN, African Union, League of Nations and 50+ more |
| 🏝️ **Territories** | 155 dependent/overseas/disputed territories |
| 🔍 **Smart search** | Accent-insensitive — searching "zilina" finds "Žilina" |
| 📑 **Pagination** | 60 flags/page, no browser-melting full loads |
| 📱 **Responsive** | Bootstrap 5, works on all screen sizes |
| ⚡ **Fast** | Lazy-loaded images, ~57 KB per page |

---

## 🚀 Quick Start

```bash
# 1. Clone / enter project
cd 2025_wt_prj_khudanych

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply database migrations
cd prj
python manage.py migrate

# 5. Populate data from Wikidata (requires internet, ~5 min)
python manage.py populate_wikidata   # 258 countries with real data
python manage.py populate_extra      # 4,400+ extra flags

# 6. Start the server
python manage.py runserver

# 7. Open in your browser
#    http://127.0.0.1:8000/
```

> **Note:** Step 5 is only needed once. The SQLite database is persisted locally after that.

---

## 📂 Project Structure

```
2025_wt_prj_khudanych/
├── requirements.txt
├── prj/
│   ├── manage.py
│   ├── app/
│   │   ├── models.py                   # Region, Country, FlagCollection
│   │   ├── views.py                    # All view functions (search, pagination)
│   │   ├── admin.py                    # Django admin config
│   │   ├── migrations/                 # DB schema migrations
│   │   ├── templates/
│   │   │   ├── base.html               # Navbar, Bootstrap, fonts
│   │   │   ├── home.html               # Landing page with stats
│   │   │   ├── countries.html          # Paginated country browser
│   │   │   ├── country_detail.html     # Single country with neighbors
│   │   │   ├── flags_gallery.html      # Gallery with lightbox & search
│   │   │   └── about.html
│   │   └── management/commands/
│   │       ├── populate_wikidata.py    # Phase 1 + 2: countries + subdivisions
│   │       └── populate_extra.py       # Historical / international / territories
│   └── prj/
│       ├── settings.py
│       └── urls.py
└── venv/                               # Virtual environment (not committed)
```

---

## 🗄️ Data Models

### `Region`
Continent-level grouping (Africa, Asia, Europe, Americas, Oceania, Antarctic).

### `Country`
| Field | Description |
|---|---|
| `name_common` / `name_official` | English names |
| `cca2` / `cca3` | ISO 3166-1 codes |
| `capital` | Capital city |
| `population` | Latest Wikidata population |
| `area` | Area in km² |
| `flag_svg` / `flag_png` / `flag_emoji` | Flag images |
| `borders` | List of neighbouring cca3 codes |
| `region` | FK to Region |

### `FlagCollection`
Stores every non-country flag. Key fields:

| Field | Description |
|---|---|
| `name` | Display name |
| `category` | `region`, `state`, `city`, `territory`, `historical`, `international`, `other` |
| `flag_image` | Wikimedia Commons thumbnail URL |
| `wikidata_id` | QID for deduplication (e.g. `Q7318` = Nazi Germany) |
| `country` | Optional FK to Country |

---

## 🔧 Management Commands

### `populate_wikidata`
Fetches countries and regional subdivisions from Wikidata SPARQL.

```bash
python manage.py populate_wikidata           # update all
python manage.py populate_wikidata --clear   # wipe and re-import
python manage.py populate_wikidata --phase 1 # countries only
python manage.py populate_wikidata --phase 2 # extra flags only
```

### `populate_extra`
Fetches historical, international, and territory flags using targeted SPARQL queries. Automatically runs deduplication at the end.

```bash
python manage.py populate_extra                        # all three categories
python manage.py populate_extra --category historical
python manage.py populate_extra --category international
python manage.py populate_extra --category territory
```

---

## 🌐 URL Routes

| URL | View | Description |
|---|---|---|
| `/` | `render_homepage` | Landing page with stats |
| `/countries/` | `countries_list` | Paginated country browser |
| `/country/<cca3>/` | `country_detail` | Single country detail |
| `/flags/` | `flags_gallery` | Full flag gallery |
| `/flags/?category=historical` | `flags_gallery` | Filtered by category |
| `/flags/?q=zilina` | `flags_gallery` | Accent-insensitive search |
| `/about/` | `render_about` | About page |
| `/admin/` | Django admin | Data management |

---

## 🛠 Tech Stack

- **Backend:** Python 3.12, Django 6.x, SQLite
- **Frontend:** Bootstrap 5.3, Bootstrap Icons, Google Fonts (Poppins)
- **Data source:** [Wikidata SPARQL](https://query.wikidata.org/) + Wikimedia Commons images
- **Search:** Unicode NFKD normalization for accent-insensitive matching

---

_Autor: Serhii Khudanych — Třída: 2.F_