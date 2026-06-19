#!/bin/sh
# Spouští se při každém startu kontejneru `web` (před gunicornem):
#  1) migrate       – vytvoří/aktualizuje schéma v SQLite na perzistentním volume
#  2) collectstatic – posbírá statické soubory do sdíleného volume, odkud je servíruje nginx
# Naplnění daty (loaddata) se NEdělá tady — to je ruční krok (playbooks/seed.yml).
set -e

echo "[entrypoint] migrate…"
python manage.py migrate --noinput

echo "[entrypoint] collectstatic…"
python manage.py collectstatic --noinput

echo "[entrypoint] spouštím: $*"
exec "$@"
