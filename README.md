# 🌍 Just Enough Flags

[![Django](https://img.shields.io/badge/Framework-Django-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Bootstrap](https://img.shields.io/badge/Style-Bootstrap_5-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com/)
[![Wikidata](https://img.shields.io/badge/Data-Wikidata-990000?logo=wikidata&logoColor=white)](https://www.wikidata.org/)

A comprehensive, database-driven geography and vexillology web application. Explore **4,600+ flags** from sovereign states, historical entities, international organizations, territories, and cities — all synchronized live from Wikidata.

---

## 📖 Odborný článek (Technical Overview)

Projekt **Just Enough Flags** představuje moderní webovou aplikaci sloužící jako komplexní databáze světových států a jejich vlajek. Z pohledu vexilologie a geografie platforma agreguje klíčová data (hlavní města, populaci, rozlohu, regiony) a efektivně je prezentuje prostřednictvím striktního oddělení přístupových práv.

### 👥 Uživatelské Role a Funkcionalita

*   **Anonymní návštěvník:** Prohlížení veřejného obsahu, vyhledávání v galerii a zobrazení detailů zemí bez nutnosti registrace.
*   **Registrovaný uživatel:** Autentizace přes standardní účet nebo **Google OAuth**. Přístup k prvkům **gamifikace** – uživatelé sbírají "hvězdičky" za prozkoumané vlajky a mohou se zapojit do komunity skrze hodnocení a komentáře.
*   **Administrátor:** Plná správa katalogu, demografických statistik a uživatelských účtů prostřednictvím dedikovaného rozhraní.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.x, Django 5.x
- **Frontend:** HTML5, CSS3, Bootstrap 5, JavaScript
- **Database:** PostgreSQL / SQLite
- **Authentication:** Django Allauth (Social Login via Google)
- **Data Source:** Wikidata SPARQL API

---

## ✨ Key Features

| Feature | Description |
|:---|:---|
| 🏳️ **Massive Gallery** | 4,600+ flags with high-quality SVG/PNG previews. |
| 📜 **Historical Context** | Flags of former states (e.g., USSR, Ottoman Empire) and 900+ more. |
| 🤝 **International Orgs** | EU, NATO, UN, and other global entities. |
| 🎮 **Gamification** | Level up your profile by exploring new flags and regions. |
| 🔍 **Advanced Search** | Accent-insensitive, smart search logic for easy discovery. |
| 📱 **Fully Responsive** | Optimized for mobile, tablet, and desktop viewing. |

---

## 📊 System Design

### User Flow & Wireframes
The application is designed with a focus on intuitive navigation and clear user journeys.

| User Flow | Wireframes |
| :---: | :---: |
| ![User Flow](docs/assets/user-flow.jpg) | ![Wireframes](docs/assets/wireframes.jpg) |

### Database Architecture (ERD)
![Entity-relationship diagram](docs/assets/FixedER.png)

---

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have Python 3.10+ and `pip` installed.

### 2. Installation & Setup
```bash
# Clone the repository
git clone https://github.com/your-repo/2025_wt_prj_khudanych.git
cd 2025_wt_prj_khudanych

# Set up virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Unix/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Database setup
cd prj
python manage.py migrate
```

### 3. Data Population
The project includes custom management commands to fetch data directly from Wikidata.
```bash
# Phase 1: 195 sovereign states + major territories
python manage.py populate_wikidata

# Phase 2: Historical, international, and extra flags
python manage.py populate_extra
```

### 4. Run Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000` to see the application in action.

---

**Autor:** Serhii Khudanych  
**Třída:** 2.F  
**License:** [MIT](LICENSE)
