from django.core.management.base import BaseCommand
from app.models import FlagCollection

class Command(BaseCommand):
    help = 'Vyepíše všechny aktuální veřejné dependence pro manuální kontrolu.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Načítám seznam veřejných dependencí...\n"))
        
        deps = FlagCollection.objects.filter(category='dependency', is_public=True).order_by('name')
        count = deps.count()
        
        self.stdout.write(self.style.SUCCESS(f"Celkem nalezeno: {count}\n"))
        self.stdout.write("-" * 80)
        
        for d in deps:
            owner_name = d.country.name_common if d.country else "BEZ VAZBY (Sirotek)"
            # Zkrátíme názvy pro přehlednost výpisu, pokud jsou moc dlouhé
            name_short = (d.name[:35] + '..') if len(d.name) > 35 else d.name
            
            self.stdout.write(f"ID: {d.id:<6} | Název: {name_short:<37} | Vazba: {owner_name}")
            
        self.stdout.write("-" * 80)
        self.stdout.write(self.style.NOTICE("Zkopíruj tento výpis a pošli ho ke kontrole!"))