from django.core.management.base import BaseCommand
from app.models import FlagCollection

class Command(BaseCommand):
    help = '🧹 Rychlý čistící skript pro skrytí mikronárodů a duplicit.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Spouštím čištění..."))

        # 1. Odstranění mikronárodů (sirotků bez vazby na Country)
        # Neměníme kategorii kvůli DB constraintu, pouze je skryjeme z frontendu
        orphans = FlagCollection.objects.filter(category='dependency', country__isnull=True)
        count = orphans.count()
        orphans.update(is_public=False)
        self.stdout.write(self.style.SUCCESS(f"✅ Vyčištěno: {count} falešných závislých území (mikronárodů) bylo trvale skryto."))

        # 2. Vyřešení duplicity Svaté Heleny
        # Použijeme .update() místo .save() - je to rychlejší a bezpečnější
        dup_updated = FlagCollection.objects.filter(id=32280).update(is_public=False)
        if dup_updated:
            self.stdout.write(self.style.SUCCESS("✅ Vyčištěno: Duplicitní vlajka Svaté Heleny byla skryta."))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Vlajka s ID 32280 nebyla nalezena."))

        self.stdout.write(self.style.NOTICE("Čištění úspěšně dokončeno!"))