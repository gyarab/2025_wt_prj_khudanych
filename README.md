# 🌍 Just Enough Flags

A database-driven geography and flags web application built with Django. Browse **4,600+ flags** from countries, historical states, international organizations, territories, cities and regions — all sourced live from [Wikidata](https://www.wikidata.org/).

---

## Odborný článek
Projekt Just Enough Flags představuje moderní webovou <u>aplikaci</u>, která slouží jako komplexní <u>databáze</u> světových <u>států</u> a jejich <u>vlajek</u>. Z pohledu <u>vexilologie</u> a <u>geografie</u> platforma agreguje klíčová <u>data</u>, mezi něž patří <u>hlavní město</u>, celková <u>populace</u>, <u>rozloha</u> a příslušný <u>kontinent</u> či geografický <u>region</u>. Systém je navržen tak, aby efektivně obsluhoval různé typy interakcí prostřednictvím striktního oddělení přístupových práv.

Základní úrovní v systému je anonymní <u>návštěvník</u>. Tento typ přístupu umožňuje volné prohlížení veřejného <u>obsahu</u>, vyhledávání specifických <u>entit</u> a používání <u>filtrů</u> v <u>galerii</u>. Návštěvník si může zobrazit detailní <u>informace</u> o konkrétní <u>zemi</u>, ale nemá možnost do systému nijak zasahovat ani zanechávat trvalou stopu.

Druhou, podstatně rozšířenou rolí, je registrovaný <u>uživatel</u>. <u>Autentizace</u> do <u>účtu</u> je řešena moderními přístupy – buď standardní kombinací e-mailu a <u>hesla</u>, nebo prostřednictvím <u>protokolu</u> Google OAuth, což výrazně usnadňuje proces registrace. Po úspěšném přihlášení získává uživatel přístup ke svému <u>profilu</u>, který obsahuje prvky <u>gamifikace</u>. Hlavním motivačním prvkem je vizuální <u>ukazatel</u> v podobě <u>hvězdiček</u> (v maximálním počtu pět), který reflektuje <u>počet</u> zhlédnutých (rozkliknutých) vlajek. Čím více států uživatel prozkoumá, tím vyšší <u>skóre</u> na profilu má. Tato role je navíc jako jediná oprávněna k interakci s komunitou, což zahrnuje udělování <u>hodnocení</u> a psaní <u>komentářů</u> k jednotlivým vexilologickým symbolům.

Nejvyšší privilegia v <u>hierarchii</u> drží <u>administrátor</u>. Jeho hlavní odpovědností je <u>správa</u> celého <u>katalogu</u>. Má <u>přístup</u> do administračního <u>rozhraní</u>, kde může přidávat nové záznamy, upravovat existující demografické <u>statistiky</u> a spravovat uživatelské účty.

Tato <u>architektura</u> zajižduje, že projekt je otevřený pro širokou veřejnost, ale zároveň poskytuje bezpečný a interaktivní prostor pro aktivní objevovatele.

### User Flow Diagram
![User Flow Diagram](docs/assets/user-flow.jpg)

### Wireframes
![Wireframes](docs/assets/wireframes.jpg)

## ✨ Features

| Feature | Details |
|---|---|
| 🏳️ **Flag gallery** | 4,600+ flags with click-to-zoom lightbox |
| 🌐 **Countries** | 195 sovereign states (UN members + Kosovo/Vatican) |
| 📜 **Historical flags** | Nazi Germany, Ottoman Empire, Soviet Union, GDR and 900+ more |
| 🤝 **International orgs** | EU, NATO, UN, African Union and 50+ more |
| 🏝️ **Territories** | 80 major and minor territories (Guam, Greenland, etc.) |
| 🔍 **Smart search** | DRY-compliant, accent-insensitive search logic |
| 📑 **Pagination** | 60 flags/page, optimized data fetching |
| 📱 **Responsive** | Bootstrap 5, works on all screen sizes |
| ⚡ **Fast** | Lazy-loaded images and specialized Django views |

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
python manage.py populate_wikidata   # Phase 1: 195 states + 54 major territories
python manage.py populate_extra      # Phase 2: Historical / international / extra flags

# 6. Start the server
python manage.py runserver
```

---

## 🗄️ Architecture & DRY

The project follows the **DRY (Don't Repeat Yourself)** principle by using a centralized normalization and pagination helper in `views.py`:

```python
def _normalize_and_paginate(items_list, request, per_page):
    # Centralized search & pagination logic
```

This ensures that search behavior, accent-insensitivity, and pagination are consistent across the Countries browser, Territories list, Historical gallery, and the main Flags Gallery.

---

_Autor: Serhii Khudanych — Třída: 2.F_
