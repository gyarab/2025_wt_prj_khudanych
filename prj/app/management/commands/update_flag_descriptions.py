import time
import os
import wikipediaapi
from django.core.management.base import BaseCommand
from app.models import FlagCollection, Country

# Local summarization imports
try:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.lsa import LsaSummarizer
    import nltk
    HAS_LOCAL_SUMMARIZER = True
except ImportError:
    HAS_LOCAL_SUMMARIZER = False

# Classic Gemini SDK (More robust for model naming)
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

class Command(BaseCommand):
    help = 'Updates flag and country descriptions from Wikipedia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit the number of records to process (0 for all)',
        )
        parser.add_argument(
            '--local',
            action='store_true',
            help='Force use of local summarizer even if Gemini key is present',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        use_local_only = options['local']
        
        # Setup AI
        api_key = os.environ.get('GOOGLE_API_KEY')
        gemini_model = None
        if api_key and HAS_GEMINI and not use_local_only:
            try:
                genai.configure(api_key=api_key)
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                self.stdout.write(self.style.SUCCESS("Using Gemini AI."))
            except Exception as e:
                self.stderr.write(f"Failed to setup Gemini: {e}. Falling back to local.")
        
        # Setup Local
        if not gemini_model:
            self.stdout.write(self.style.WARNING("Using local summarizer."))
            try:
                nltk.download('punkt', quiet=True)
                nltk.download('punkt_tab', quiet=True)
            except: pass

        # Setup Wiki
        wiki = wikipediaapi.Wikipedia(
            user_agent='FlagProject/1.0 (contact@example.com)',
            language='en',
            extract_format=wikipediaapi.ExtractFormat.WIKI
        )

        # 1. Fetch Countries that need description (using Currencies temp check as proxy for test)
        # In a real app, you'd have a 'description' field on Country too.
        # For this test, I'll update the 'description' of any matching Country or FlagCollection.
        
        # Get Czechia specifically as requested
        targets = []
        czech = Country.objects.filter(name_common__icontains='Czech').first()
        if czech:
            targets.append(('country', czech))

        # Add other flags if no czech found or limit allows
        if len(targets) < (limit if limit > 0 else 9999):
            flags = FlagCollection.objects.all()
            for f in flags:
                desc = f.description
                if not isinstance(desc, dict): desc = {}
                if not desc.get('en'):
                    targets.append(('flag', f))
                    if limit > 0 and len(targets) >= limit: break

        for type_name, obj in targets:
            name = obj.name_common if type_name == 'country' else obj.name
            self.stdout.write(f'Processing: {name}')
            
            # Search terms
            search_terms = [name, f"Flag of {name}", f"Flag of the {name}"] if type_name == 'country' else [f"Flag of {name}", name]
            
            summary = None
            for term in search_terms:
                try:
                    page = wiki.page(term)
                    if page.exists() and len(page.summary) > 100:
                        summary = page.summary
                        break
                except: continue
            
            if not summary:
                self.stderr.write(self.style.WARNING(f'Could not find Wiki for {name}'))
                continue

            try:
                html_content = None
                if gemini_model:
                    try:
                        prompt = f"Summarize '{name}' into 3-4 concise HTML bullet points (<ul><li>). Return ONLY HTML.\n\nContext:\n{summary}"
                        response = gemini_model.generate_content(prompt)
                        html_content = response.text.strip()
                        if '```' in html_content:
                            html_content = html_content.split('```')[1].replace('html', '').strip()
                    except: 
                        gemini_model = None

                if not html_content:
                    parser = PlaintextParser.from_string(summary, Tokenizer("english"))
                    summarizer = LsaSummarizer()
                    sentences = summarizer(parser.document, 3)
                    html_content = "<ul>" + "".join([f"<li>{s}</li>" for s in sentences]) + "</ul>"

                # Save (Using FlagCollection as the primary store for results as per your initial request)
                # If we found a Country, let's see if there's a corresponding flag in FlagCollection
                if type_name == 'country':
                    # Create or get a FlagCollection entry for this country to store the result
                    flag_obj, _ = FlagCollection.objects.get_or_create(
                        name=name,
                        defaults={'category': 'other'}
                    )
                else:
                    flag_obj = obj
                
                if not isinstance(flag_obj.description, dict): flag_obj.description = {}
                flag_obj.description['en'] = html_content
                flag_obj.save()
                self.stdout.write(self.style.SUCCESS(f'Updated {name} in database.'))
                
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Error processing {name}: {e}'))

            time.sleep(2 if gemini_model else 0.5)
