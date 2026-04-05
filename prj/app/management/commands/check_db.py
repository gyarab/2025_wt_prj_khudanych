from django.core.management.base import BaseCommand
from django.db.models import Count
from app.models import FlagCollection

class Command(BaseCommand):
    help = 'Databázová telemetrie: Kontrola kategorií a detekce duplicitních obrázků.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Startuji hloubkovou analýzu databáze...\n"))

        # =====================================================================
        # 1. ANALÝZA KATEGORIÍ (Diagnostika prázdného filtru 'Countries')
        # =====================================================================
        self.stdout.write(self.style.WARNING("--- 1. ANALÝZA KATEGORIÍ V DB ---"))
        
        categories = FlagCollection.objects.values('category').annotate(count=Count('id')).order_by('-count')
        
        country_count = 0
        dependency_count = 0
        for cat in categories:
            cat_name = cat['category'] if cat['category'] else "NULL / Prázdné"
            self.stdout.write(f" - '{cat_name}': {cat['count']} vlajek")
            if cat_name == 'country':
                country_count = cat['count']
            if cat_name == 'dependency':
                dependency_count = cat['count']

        self.stdout.write(self.style.SUCCESS("\n💡 INFO PRO FRONTEND:"))
        self.stdout.write(f"Frontend používá '?category=country' pro suverénní státy ({country_count} položek).")
        self.stdout.write(f"Frontend používá '?category=dependency' pro nesuverénní území ({dependency_count} položek).\n\n")

        # =====================================================================
        # 2. ANALÝZA DUPLICIT (Používáme pole 'flag_image')
        # =====================================================================
        self.stdout.write(self.style.WARNING("--- 2. DETEKCE VLAJEK SE STEJNÝM OBRÁZKEM ---"))
        
        # Seskupíme podle skutečného názvu pole: flag_image
        duplicity_qs = FlagCollection.objects.values('flag_image').annotate(
            url_count=Count('id')
        ).filter(url_count__gt=1).exclude(flag_image__isnull=True).exclude(flag_image__exact='').order_by('-url_count')
        
        total_duplicates = duplicity_qs.count()
        self.stdout.write(f"Nalezeno {total_duplicates} unikátních obrázků sdílených více entitami.\n")

        limit = 15
        self.stdout.write(f"Zobrazuji prvních {limit} ukázek:\n")
        
        for dup in duplicity_qs[:limit]:
            img_val = dup['flag_image']
            count = dup['url_count']
            
            # Zkrácení cesty pro terminál
            short_name = str(img_val).split('/')[-1]
            
            self.stdout.write(self.style.NOTICE(f"\n🔗 Obrázek sdílen {count}x: .../{short_name}"))
            
            # Najdeme všechny vlajky s tímto obrázkem
            flags = FlagCollection.objects.filter(flag_image=img_val).order_by('name')
            for f in flags:
                wiki_info = f"QID: {f.wikidata_id}" if f.wikidata_id else "Bez QID"
                self.stdout.write(f"   🚩 ID: {f.id:<5} | Kat: {str(f.category):<10} | Jméno: {f.name:<30} | {wiki_info}")

        self.stdout.write(self.style.SUCCESS("\n🏁 Telemetrie dokončena."))