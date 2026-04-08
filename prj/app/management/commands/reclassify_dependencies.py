from django.core.management.base import BaseCommand
from app.models import FlagCollection

class Command(BaseCommand):
    help = 'Přeřadí falešné dependence (města, regiony) do správných kategorií.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Spouštím přeřazování kategorií..."))

        # Mapování ID -> Nová kategorie
        reclass_map = {
            # --- MĚSTA A OBCE (city) ---
            26207: 'city',  # Artsyz urban hromada
            26208: 'city',  # Horodnie rural hromada
            20294: 'city',  # Frielas
            31024: 'city',  # Huancayo District
            31329: 'city',  # Kozushima
            31822: 'city',  # Mannō-chō (Japonsko)
            20185: 'city',  # Santa Cruz da Graciosa
            33598: 'city',  # Schermer
            32896: 'city',  # Vlieland
            33601: 'city',  # Zeevang
            29513: 'city',  # Wangerooge
            30153: 'city',  # Maupiti (commune)
            30009: 'city',  # Huahine

            # --- REGIONY A OSTROVY (region) ---
            28464: 'region',  # Easter Island
            18288: 'region',  # Federal Dependencies of Venezuela
            31199: 'region',  # Francisco de Miranda Insular Territ..
            17945: 'region',  # Johnston Atoll
            33946: 'region',  # La Palma
            18804: 'region',  # Lundy
            29930: 'region',  # Madeira
            18398: 'region',  # Nevis
            31288: 'region',  # Rodrigues
            32993: 'region',  # Santa Catalina
            31697: 'region',  # Scattered Islands in the Indian Oce..
            28125: 'region',  # Swains Island
            26417: 'region',  # Occupied Palestinian territories
            
            # Francouzská Polynésie (Ostrovy jako regiony)
            30190: 'region',  # Fatu-Hiva
            29945: 'region',  # Raivavae
            30164: 'region',  # Rapa
            30156: 'region',  # Reao
            29560: 'region',  # Rimatara
            29565: 'region',  # Rurutu
            29568: 'region',  # Tahuata
            29559: 'region',  # Ua-Huka
            29575: 'region',  # Ua-Pou

            # --- STÁTY (country) ---
            27257: 'country', # Kosovo
        }

        success_count = 0
        for flag_id, new_category in reclass_map.items():
            updated = FlagCollection.objects.filter(id=flag_id).update(category=new_category)
            if updated:
                success_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Úspěšně přeřazeno {success_count} záznamů ze {len(reclass_map)}."))
        
        # Pojistka pro Svatou Helenu - "Saint Helena" je jen část (region) celku "Saint Helena, Ascension and Tristan da Cunha"
        # Máš tam Svatou Helenu ID 31898. Dáme jí kategorii 'region', aby nekonkurovala celé dependenci
        helena = FlagCollection.objects.filter(id=31898).update(category='region')
        if helena:
            self.stdout.write(self.style.SUCCESS("✅ Ostrov Svatá Helena (ID 31898) byl přeřazen do regionů, aby neblokoval hlavní dependenci."))

        self.stdout.write(self.style.NOTICE("Hotovo! Zkontroluj galerii na webu."))