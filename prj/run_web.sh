#!/bin/bash

# Definujeme si cesty absolutně, aby nebyl prostor pro chybu
PROJECT_DIR="/home/serhii.khudanych.s/2025_wt_prj_khudanych/prj"
VENV_PATH="/home/serhii.khudanych.s/2025_wt_prj_khudanych/prj/venv"

echo "=== STARTUJI JEF WEB (Tmux Mode) ==="

# 1. Aktivace prostředí
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "OK: Virtuální prostředí aktivováno."
else
    echo "ERROR: Venv nenalezen v $VENV_PATH!"
    exit 1
fi

# 2. Skok do složky s manage.py
cd "$PROJECT_DIR"

# 3. Práce s Django
python manage.py collectstatic --noinput

# 4. Port cleanup
fuser -k 11210/tcp 2>/dev/null
sleep 1

# 5. Gunicorn launch
echo "Startuji Gunicorn na portu 11210..."
exec gunicorn prj.wsgi:application \
    --bind 0.0.0.0:11210 \
    --workers 3 \
    --timeout 120
