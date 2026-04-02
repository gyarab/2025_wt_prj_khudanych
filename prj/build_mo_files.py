#!/usr/bin/env python3
"""
Build .mo files from .po files without requiring system gettext.
This script uses polib to compile Django translation files.

Usage: python build_mo_files.py
"""
import os
import sys
from pathlib import Path

try:
    import polib
except ImportError:
    print("ERROR: polib is not installed. Run: pip install polib")
    sys.exit(1)


def compile_po_to_mo(po_file_path):
    """Compile a single .po file to .mo format."""
    try:
        po = polib.pofile(str(po_file_path))
        mo_file_path = po_file_path.with_suffix('.mo')
        
        # Save as .mo file
        po.save_as_mofile(str(mo_file_path))
        
        return True, mo_file_path
    except Exception as e:
        return False, str(e)


def main():
    """Find all django.po files and compile them to django.mo."""
    # Get the directory where this script is located (next to manage.py)
    script_dir = Path(__file__).resolve().parent
    locale_dir = script_dir / 'locale'
    
    print("=" * 60)
    print("Django Translation Compiler (Python-only, no gettext)")
    print("=" * 60)
    print(f"Script location: {script_dir}")
    print(f"Locale directory: {locale_dir}")
    print()
    
    if not locale_dir.exists():
        print(f"ERROR: Locale directory not found: {locale_dir}")
        sys.exit(1)
    
    # Find all django.po files
    po_files = list(locale_dir.glob('*/LC_MESSAGES/django.po'))
    
    if not po_files:
        print("WARNING: No django.po files found in locale/ directory")
        sys.exit(0)
    
    print(f"Found {len(po_files)} translation file(s) to compile:")
    for po_file in po_files:
        print(f"  • {po_file.relative_to(script_dir)}")
    print()
    
    # Compile each .po file
    success_count = 0
    error_count = 0
    
    for po_file in po_files:
        lang_code = po_file.parent.parent.name
        print(f"Compiling {lang_code}...", end=" ")
        
        success, result = compile_po_to_mo(po_file)
        
        if success:
            print(f"✓ SUCCESS")
            print(f"  → Created: {result.relative_to(script_dir)}")
            success_count += 1
        else:
            print(f"✗ FAILED")
            print(f"  → Error: {result}")
            error_count += 1
    
    print()
    print("=" * 60)
    print(f"Compilation complete: {success_count} succeeded, {error_count} failed")
    print("=" * 60)
    
    if error_count > 0:
        sys.exit(1)
    
    # Verify .mo files were created
    print()
    print("Verifying compiled files:")
    for po_file in po_files:
        mo_file = po_file.with_suffix('.mo')
        lang_code = po_file.parent.parent.name
        if mo_file.exists():
            size_kb = mo_file.stat().st_size / 1024
            print(f"  ✓ {lang_code}: {mo_file.name} ({size_kb:.1f} KB)")
        else:
            print(f"  ✗ {lang_code}: {mo_file.name} NOT FOUND")
    
    print()
    print("✅ Translation files are ready!")
    print("   You can now run: python manage.py runserver")
    print("   Test URLs:")
    print("     • http://localhost:8000/en/  (English)")
    print("     • http://localhost:8000/cs/  (Czech)")
    print("     • http://localhost:8000/de/  (German)")


if __name__ == '__main__':
    main()
