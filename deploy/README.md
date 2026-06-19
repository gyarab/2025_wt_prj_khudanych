# Nasazení JEF (deployment)

Tahle složka přidává **nasazení aplikace na reálný server**. Je adaptovaná podle
referenčního projektu předmětu Webové technologie (FilmDB). Aplikaci zabalíme do
kontejnerů a pošleme ji na server přes **Ansible**, celé to spouští **GitHub Actions**
a provoz zvenčí na ni pouští **traefik** (reverzní proxy na serveru).

> Lokální vývoj se nemění — dál platí `./manage.py runserver` + `pnpm dev`
> z hlavního [README](../README.md). Tady je řeč jen o produkci.

> ⚠️ **Než nasadíš:** doplň přístupy, které dostaneš později — hledej `CHANGEME` v
> [inventory.ini](inventory.ini) a [config/production.env](config/production.env)
> (doména `APP_HOST`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`,
> `ansible_host`, `ansible_user`, `project_dir`) a vygeneruj si vlastní `DJANGO_SECRET_KEY`.

## Jak to vypadá na serveru

```
                       ┌──────────────────── server ─────────────────────────────────────┐
                       │  traefik  (HTTPS / Let's Encrypt, síť `proxy`)                    │
 návštěvník ──HTTPS──► │     │  Host(${APP_HOST})                                          │
                       │     ▼                                                             │
                       │  frontend (nginx)                                                 │
                       │    /app/     →  Vue SPA (build z frontend/)                       │
                       │    /static/  →  statika Djanga   (volume static_data)             │
                       │    /media/   →  média            (volume media_data)              │
                       │    /…        →  proxy ──► web (gunicorn :8000)   [síť `internal`] │
                       │                          Django: /, /flags, /admin, /api          │
                       │                          SQLite (volume db_data)                  │
                       └───────────────────────────────────────────────────────────────────┘
```

Dvě služby (viz [docker-compose.yml](docker-compose.yml)):

| služba | image | co dělá |
|--------|-------|---------|
| `web` | [../Dockerfile](../Dockerfile) | Django + gunicorn. Při startu pustí `migrate` a `collectstatic` (viz [web-entrypoint.sh](web-entrypoint.sh)). |
| `frontend` | [../frontend/Dockerfile](../frontend/Dockerfile) | nginx = vstupní brána. Postaví Vue SPA (pnpm) a servíruje statiku/média + proxuje na `web`. |

Dva frontendy nad stejným backendem koexistují tak, že **Django zůstává v kořeni**
(`/`, `/flags`, `/admin`, `/api`, `/playground`) a **Vue SPA se přesune pod `/app/`**
(build s `VITE_BASE=/app/`, router používá `import.meta.env.BASE_URL`).

## Konfigurace

- [inventory.ini](inventory.ini) — **verzovaný** seznam serverů. Uprav `ansible_host`
  (kam) a `ansible_user` (jako kdo). `project_dir` je cesta na serveru, kam se
  rozbalí zdroják.
- [config/production.env](config/production.env) — **necitlivé** nastavení (doména
  `APP_HOST`, traefik entrypoint/certresolver, DEBUG, ALLOWED_HOSTS, cesty k datům).
  Commitnuté schválně.
- **Jediné tajemství** je SSH klíč v GitHub secrets jako `SSH_PRIVATE_KEY`
  (Settings → Secrets and variables → Actions). Veřejnou půlku klíče přidej do
  `~/.ssh/authorized_keys` uživatele `ansible_user` na serveru. Ten uživatel musí
  umět spouštět `docker`.

> ⚠️ Bezpečnost je tu **záměrně zjednodušená** (školní projekt): `SECRET_KEY` i
> ostatní nastavení jsou v gitu, ven jde jen SSH klíč přes secret. Pro ostrý provoz
> by tajemství patřila do secrets / vaultu, ne do repa.

## Nasazení přes GitHub Actions

Dva oddělené workflowy:

- **Deploy** ([.github/workflows/deploy.yml](../.github/workflows/deploy.yml)) — nasadí
  kód. Spustí se automaticky při pushi do `main`, nebo ručně (Actions → *Deploy* →
  *Run workflow*). Data v databázi zůstanou.
- **Seed database** ([.github/workflows/seed.yml](../.github/workflows/seed.yml)) — jen
  ručně. Znovu naplní databázi z `fixtures/countries.json` (**POZOR: napřed ji
  vyprázdní**). Pro potvrzení se do pole *confirm* píše `SEED`, nebo přes CLI:
  `gh workflow run "Seed database" -f confirm=SEED`.

## Ruční nasazení (bez Actions)

Z této složky (potřebuješ SSH přístup na server + nainstalovaný Ansible):

```bash
pip install ansible-core
ansible-galaxy collection install community.docker

# nasazení (build + up)
ansible-playbook playbooks/deploy.yml

# naplnění daty — POZOR: napřed databázi vyprázdní (flush), pak nahraje countries.json
ansible-playbook playbooks/seed.yml
```

Co playbooky dělají:

- [playbooks/deploy.yml](playbooks/deploy.yml) — `git archive HEAD` zabalí commitnutý
  stav, pošle ho na server do `project_dir`, tam `docker compose up -d --build`.
  Migrace a collectstatic doběhnou z entrypointu kontejneru.
- [playbooks/seed.yml](playbooks/seed.yml) — `manage.py flush` + `loaddata
  /app/fixtures/countries.json` uvnitř kontejneru `web` (fixture je zabalený v image).

## Spustit celý stack přímo na serveru (debug)

```bash
cd <project_dir>/deploy   # = project_dir z inventory.ini
docker compose --env-file config/production.env -f docker-compose.yml up -d --build
docker compose --env-file config/production.env -f docker-compose.yml logs -f web
```

## Předpoklady na serveru

- Nainstalovaný Docker + plugin `docker compose`.
- `ansible_user` smí používat docker a má v `authorized_keys` veřejný klíč k `SSH_PRIVATE_KEY`.
- Běžící **traefik** se sdílenou externí sítí **`proxy`** (entrypoint `websecure`,
  certresolver `letsencrypt` — názvy uprav v `production.env`, pokud má platforma jiné).
  Síť musí existovat předem: `docker network create proxy`.
- **DNS** pro `${APP_HOST}` míří na server (aby traefik dostal Let's Encrypt cert).
