from django.core.management.base import BaseCommand
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = 'Přesune popisy a překlady z FlagCollection do Country a smaže duplikáty.'

    def handle(self, *args, **kwargs):
        # Najdeme všechny vlajky, co jsou označené jako 'dependency'
        dependencies = FlagCollection.objects.filter(category='dependency')
        
        self.stdout.write(f"Nalezeno {dependencies.count()} záznamů ve FlagCollection k vyřešení.")

        for flag in dependencies:
            if flag.country: # Pokud je vlajka správně propojená s tabulkou Country
                country = flag.country
                
                # Vysajeme data z FlagCollection a uložíme je do Country
                updated = False
                
                # Pokud Country ještě nemá český popis, vezmeme ho z JSON description kolekce
                if not country.description and flag.description:
                    # Předpokládám, že ve flag.description máš {"cs": "Historie Anguilly..."} podle screenu
                    desc_dict = flag.description if isinstance(flag.description, dict) else {}
                    country.description = desc_dict.get('cs', '') or str(flag.description)
                    updated = True
                
                if not country.name_cs and flag.name_cs:
                    country.name_cs = flag.name_cs
                    updated = True
                    
                if not country.name_de and flag.name_de:
                    country.name_de = flag.name_de
                    updated = True

                if updated:
                    country.save()
                    self.stdout.write(self.style.SUCCESS(f"✅ Aktualizována data pro {country.name_common}"))
                
                # Nyní můžeme bezpečně smazat duplikát z FlagCollection!
                flag.delete()
                self.stdout.write(self.style.WARNING(f"🗑️ Smazán duplikát z FlagCollection: {flag.name}"))
            
            else:
                self.stdout.write(self.style.ERROR(f"❌ Vlajka {flag.name} nemá přiřazenou Country! (Sirotek)"))

        self.stdout.write(self.style.SUCCESS("\nHotovo. Databáze je čistá!"))