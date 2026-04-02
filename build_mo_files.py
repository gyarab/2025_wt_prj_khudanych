#!/usr/bin/env python3
"""
Build .mo files from .po files without requiring system gettext.
Run this script from the repository root.
"""
import sys
from pathlib import Path

try:
    import polib
except ImportError:
    print("ERROR: polib is not installed. Run: pip install polib")
    sys.exit(1)


def compile_po_to_mo(po_file_path: Path):
    """Compile a single .po file to .mo format."""
    try:
        po = polib.pofile(str(po_file_path))
        mo_file_path = po_file_path.with_suffix('.mo')
        po.save_as_mofile(str(mo_file_path))
        return True, mo_file_path
    except Exception as exc:
        return False, str(exc)


def main():
    script_dir = Path(__file__).resolve().parent
    locale_dir = script_dir / 'prj' / 'locale'

    print("=" * 60)
    print("Django Translation Compiler (Python-only, no gettext)")
    print("=" * 60)
    print(f"Script location: {script_dir}")
    print(f"Locale directory: {locale_dir}")
    print()

    if not locale_dir.exists():
        print(f"ERROR: Locale directory not found: {locale_dir}")
        sys.exit(1)

    po_files = sorted(locale_dir.glob('*/LC_MESSAGES/django.po'))
    if not po_files:
        print("WARNING: No django.po files found in prj/locale/")
        sys.exit(0)

    print(f"Found {len(po_files)} translation file(s):")
    for po_file in po_files:
        print(f"  - {po_file.relative_to(script_dir)}")
    print()

    success_count = 0
    error_count = 0

    for po_file in po_files:
        lang_code = po_file.parent.parent.name
        print(f"Compiling {lang_code}...", end=" ")

        success, result = compile_po_to_mo(po_file)
        if success:
            print("OK")
            print(f"  Created: {result.relative_to(script_dir)}")
            success_count += 1
        else:
            print("FAILED")
            print(f"  Error: {result}")
            error_count += 1

    print()
    print("=" * 60)
    print(f"Compilation complete: {success_count} succeeded, {error_count} failed")
    print("=" * 60)

    if error_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
