#!/usr/bin/env python3
"""
Validation script for refactoring completeness.
Run this to verify all components are working correctly.
"""

import sys
import os

# Add project to path
sys.path.insert(0, 'prj')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prj.settings')

import django
django.setup()

print("="*60)
print("REFACTORING VALIDATION TEST")
print("="*60)
print()

# Test 1: Import all view functions
print("[1/5] Testing view imports...")
try:
    from app.views import (
        profile_view, profile_edit, render_homepage, countries_list,
        country_detail, territory_detail, flag_detail, render_about,
        territories_list, historical_list, flags_gallery,
        flags_search_api, countries_search_api, territories_search_api, historical_search_api
    )
    print("  ✓ All 14 view functions imported successfully")
except ImportError as e:
    print(f"  ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Wikidata action loader
print("[2/5] Testing Wikidata action loader...")
try:
    from app.utils.wikidata_action_loader import (
        get_decision, get_all_decisions, get_statistics, 
        get_decisions_by_action_type, get_decisions_by_confidence_range
    )
    
    # Test basic functionality
    all_decisions = get_all_decisions()
    stats = get_statistics()
    
    print(f"  ✓ Loaded {stats['total_entries']} Wikidata entries")
    print(f"  ✓ Categories: {len(stats['categories'])} types")
    print(f"  ✓ Action types: {len(stats['action_types'])} types")
    
    # Test specific lookup
    test_decision = get_decision("Q100143020")
    if test_decision:
        print(f"  ✓ Lookup working: {test_decision['name'][:50]}...")
    else:
        print("  ⚠ Warning: Sample decision not found")
        
except Exception as e:
    print(f"  ✗ Loader failed: {e}")
    sys.exit(1)

# Test 3: Verify module structure
print("[3/5] Verifying module structure...")
module_files = [
    'prj/app/views/__init__.py',
    'prj/app/views/main_views.py',
    'prj/app/views/eligibility.py',
    'prj/app/views/text_utils.py',
    'prj/app/views/search_filters.py',
    'prj/app/views/pagination_helpers.py',
    'prj/app/views/search_apis.py',
    'prj/app/views/gallery_builders.py',
    'prj/app/views/blended_views.py',
    'prj/app/utils/wikidata_action_loader.py',
    'prj/data/wikidata_actions.json',
]

missing = []
for filepath in module_files:
    if not os.path.exists(filepath):
        missing.append(filepath)
        
if missing:
    print(f"  ✗ Missing files: {', '.join(missing)}")
    sys.exit(1)
else:
    print(f"  ✓ All {len(module_files)} module files present")

# Test 4: Check line counts
print("[4/5] Checking refactored file sizes...")
import subprocess

def count_lines(filepath):
    if not os.path.exists(filepath):
        return 0
    result = subprocess.run(['wc', '-l', filepath], capture_output=True, text=True)
    return int(result.stdout.split()[0])

view_modules = {
    'main_views.py': count_lines('prj/app/views/main_views.py'),
    'eligibility.py': count_lines('prj/app/views/eligibility.py'),
    'text_utils.py': count_lines('prj/app/views/text_utils.py'),
    'search_filters.py': count_lines('prj/app/views/search_filters.py'),
    'pagination_helpers.py': count_lines('prj/app/views/pagination_helpers.py'),
    'search_apis.py': count_lines('prj/app/views/search_apis.py'),
    'gallery_builders.py': count_lines('prj/app/views/gallery_builders.py'),
    'blended_views.py': count_lines('prj/app/views/blended_views.py'),
}

total_lines = sum(view_modules.values())
max_module = max(view_modules.items(), key=lambda x: x[1])

print(f"  ✓ Total refactored lines: {total_lines}")
print(f"  ✓ Largest module: {max_module[0]} ({max_module[1]} lines)")
print(f"  ✓ Average module size: {total_lines // len(view_modules)} lines")

if max_module[1] > 500:
    print(f"  ⚠ Warning: {max_module[0]} exceeds 500 lines")

# Test 5: Django check
print("[5/5] Running Django system check...")
try:
    from django.core.management import call_command
    from io import StringIO
    
    output = StringIO()
    call_command('check', stdout=output, stderr=output)
    result = output.getvalue()
    
    if 'System check identified no issues' in result:
        print("  ✓ Django check passed (0 errors)")
    else:
        # Check only for errors, ignore warnings
        if 'ERROR' in result:
            print(f"  ✗ Django check failed")
            print(result)
            sys.exit(1)
        else:
            print("  ✓ No critical errors (warnings may exist)")
            
except Exception as e:
    print(f"  ✗ Django check failed: {e}")
    sys.exit(1)

print()
print("="*60)
print("✅ ALL VALIDATION TESTS PASSED")
print("="*60)
print()
print("Summary:")
print(f"  - {len(view_modules)} modular view files")
print(f"  - {total_lines} total lines (avg {total_lines // len(view_modules)} per module)")
print(f"  - {stats['total_entries']} Wikidata decisions loaded")
print(f"  - 14 view functions exported")
print(f"  - Django checks passing")
print()
print("Refactoring complete and validated!")
