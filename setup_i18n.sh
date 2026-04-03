#!/bin/bash
# Localization setup script for Just Enough Flags project

set -e

echo "========================================="
echo "Just Enough Flags - Localization Setup"
echo "========================================="
echo ""

cd /home/serhii.khudanych.s/2025_wt_prj_khudanych/prj

# Ensure locale directories exist
echo "[1/4] Creating locale directories..."
mkdir -p locale/cs/LC_MESSAGES
mkdir -p locale/de/LC_MESSAGES
mkdir -p app/locale/cs/LC_MESSAGES
mkdir -p app/locale/de/LC_MESSAGES

# Generate message files for project-level translations
echo "[2/4] Generating message files (project level)..."
python3 manage.py makemessages -l cs -l de --ignore=venv

# Generate message files for app-level translations
echo "[3/4] Generating message files (app level)..."
cd app
python3 ../manage.py makemessages -l cs -l de --ignore=venv --ignore=migrations
cd ..

# Compile all message files
echo "[4/4] Compiling message files..."
python3 manage.py compilemessages --ignore=venv

echo ""
echo "✓ Localization setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .po files in locale/cs/LC_MESSAGES/ and locale/de/LC_MESSAGES/"
echo "  2. Run: python3 manage.py compilemessages"
echo "  3. Restart Django development server"
echo ""
echo "To update translations after code changes:"
echo "  python3 manage.py makemessages -a --ignore=venv"
echo "  python3 manage.py compilemessages --ignore=venv"
echo ""
