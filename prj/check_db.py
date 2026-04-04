import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prj.settings') # Uprav podle názvu tvé složky s nastavením
django.setup()

from app.models import FlagCollection, Country
from django.db.models import Count

def run_health_check():
    print("="*50)
    print("🔍 JUST ENOUGH FLAGS - DATABASE HEALTH CHECK")
    print("="*50)

    # Statistika kategorií
    print("\n📊 ROZLOŽENÍ KATEGORIÍ:")
    cats = FlagCollection.objects.values('category').annotate(total=Count('id')).order_by('-total')
    for c in cats:
        print(f"  - {c['category']:<15}: {c['total']} vlajek")

    # Kontrola Bindingu (Přiřazení k zemím)
    print("\n🔗 BINDING STATS:")
    bound = FlagCollection.objects.filter(country__isnull=False).count()
    unbound = FlagCollection.objects.filter(country__isnull=True).count()
    print(f"  - Přiřazeno k zemi:  {bound}")
    print(f"  - Bez země:          {unbound}")

    # Kontrola názvů (Disambiguation check)
    print("\n⚠️ DUPLICITNÍ NÁZVY (Stále hrozí záměna Aberdeenů?):")
    dupes = FlagCollection.objects.values('name').annotate(cnt=Count('id')).filter(cnt__gt=1).order_by('-cnt')
    if dupes.exists():
        for d in dupes[:15]:
            qids = list(FlagCollection.objects.filter(name=d['name']).values_list('wikidata_id', flat=True))
            print(f"  - '{d['name']}' ({d['cnt']}x) | QIDs: {', '.join(qids)}")
    else:
        print("  ✅ Žádné duplicitní názvy! Skript s dlouhými jmény zafungoval.")

    # Stav verifikace AI agentem
    print("\n🤖 AI AGENT PROGRESS:")
    verified = FlagCollection.objects.filter(is_verified=True).count()
    total = FlagCollection.objects.count()
    percent = (verified / total * 100) if total > 0 else 0
    print(f"  - Hotovo: {verified} / {total} ({percent:.1f} %)")

if __name__ == "__main__":
    run_health_check()