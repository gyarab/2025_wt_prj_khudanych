import json
import time
import os
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from app.models import FlagCollection

load_dotenv()

class Command(BaseCommand):
    help = 'Survivor AI agent: Zvládne Extra data i 500 chyby.'

    def add_arguments(self, parser):
        # S vyhledáváním je bezpečnější menší balík, aby AI "nevytekly nervy"
        parser.add_argument('--chunk-size', type=int, default=50)

    def extract_json(self, text):
        """Pokusí se najít a vyparsovat JSON i v bordelu kolem."""
        try:
            # Najde vše mezi první { a poslední }
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(text)
        except:
            return None

    def handle(self, *args, **options):
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        chunk_size = options['chunk_size']

        flags = FlagCollection.objects.filter(is_verified=False, is_public=True)
        total = flags.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("Všechny vlajky jsou ověřené."))
            return

        for i in range(0, total, chunk_size):
            chunk = flags[i:i + chunk_size]
            batch_num = i // chunk_size + 1
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n[Batch {batch_num}] Zpracovávám {len(chunk)} položek..."))
            
            data_to_send = [{"id": str(f.wikidata_id), "name": f.name} for f in chunk]

            prompt = f"""
            Find EXACT population and area for these {len(data_to_send)} items using Google Search.
            Return ONLY JSON: {{"QID": {{"population": int, "area_km2": float, "lat": float, "lon": float}}}}
            DATA: {json.dumps(data_to_send)}
            """

            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash', # Zkus i 'gemini-1.5-flash' pokud dojde limit
                    contents=prompt,
                    config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
                )
                
                ai_results = self.extract_json(response.text)
                
                if not ai_results:
                    self.stdout.write(self.style.ERROR("Nepodařilo se vypreparovat JSON z odpovědi."))
                    continue

                for flag in chunk:
                    res = ai_results.get(str(flag.wikidata_id))
                    if res:
                        flag.population = res.get('population') or flag.population
                        flag.area_km2 = res.get('area_km2') or flag.area_km2
                        flag.latitude = res.get('lat') or flag.latitude
                        flag.longitude = res.get('lon') or flag.longitude
                        flag.is_verified = True
                        flag.save()
                
                self.stdout.write(self.style.SUCCESS(f"Balík {batch_num} uložen."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Batch {batch_num} selhal: {e}"))
                if "429" in str(e): 
                    self.stdout.write(self.style.NOTICE("Dneska padla. Zbytek doděláme zítra!"))
                    break
            
            time.sleep(10)