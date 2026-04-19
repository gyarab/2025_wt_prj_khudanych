#!/bin/bash



# Zjistíme, kde přesně jsme

CURRENT_DIR=$(pwd)

VENV_PATH="$(dirname "$CURRENT_DIR")/prj/venv"



echo "=== STARTUJI JEF WEB ==="



# 1. NASTAVENÍ PRODUKČNÍHO PROSTŘEDÍ (BEZPEČNOST)

export DJANGO_ENV="production"

# Tohle je tvůj nový produkční klíč. Nikomu ho neukazuj a nedávej ho na GitHub.

export DJANGO_SECRET_KEY="wSd5E__9Bgp9bHQ7OoL7XEfAjyl55Bvge8Y614jxAAWX3G9Z4MWaYnwWgkMxlBr54ms"



# 2. Aktivace virtuálního prostředí

if [ -f "$VENV_PATH/bin/activate" ]; then

    source "$VENV_PATH/bin/activate"

    echo "OK: Virtuální prostředí aktivováno."

else

    echo "ERROR: Venv v '$VENV_PATH' fakt není. Zkontroluj cestu!"

    exit 1

fi



# 3. Příprava statických souborů

python manage.py collectstatic --noinput



# 4. Úklid starých procesů na portu

fuser -k 11210/tcp 2>/dev/null

sleep 1



# 5. Start Gunicornu v produkčním režimu

echo "Nahažuji Gunicorn na portu 11210..."

exec gunicorn prj.wsgi:application --bind 0.0.0.0:11210 --workers 3 --timeout 120
