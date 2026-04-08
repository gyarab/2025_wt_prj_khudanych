from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Dynamický výpis všech tabulek a jejich polí v databázi.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("="*80))
        self.stdout.write(self.style.NOTICE("🚀 SPOUŠTÍM KOMPLEXNÍ VÝPIS DATABÁZOVÉHO SCHÉMATU"))
        self.stdout.write(self.style.NOTICE("="*80 + "\n"))

        # Získáme úplně všechny modely ze všech nainstalovaných aplikací (včetně systémových)
        all_models = apps.get_models()

        for model in all_models:
            app_label = model._meta.app_label
            model_name = model.__name__
            db_table = model._meta.db_table

            # Hlavička pro každý model
            self.stdout.write(self.style.SUCCESS(f"\n📦 APLIKACE: {app_label} | MODEL: {model_name} | DB TABULKA: {db_table}"))
            self.stdout.write("-" * 80)
            self.stdout.write(f"{'NÁZEV POLE':<25} | {'TYP POLE':<25} | {'VLASTNOSTI / VAZBA'}")
            self.stdout.write("-" * 80)

            # Získáme všechna pole daného modelu
            for field in model._meta.get_fields():
                field_name = field.name
                field_type = field.__class__.__name__

                details = []
                
                # Zjištění, zda jde o relaci (cizí klíč, M2M atd.)
                if field.is_relation:
                    related_model = field.related_model
                    if related_model:
                        details.append(f"Vazba na -> {related_model.__name__}")
                    else:
                        details.append("Zpětná/Generická vazba")

                # Zjištění dalších užitečných vlastností pole
                if hasattr(field, 'primary_key') and field.primary_key:
                    details.append("Primary Key (PK)")
                if hasattr(field, 'null') and field.null:
                    details.append("NULL")
                if hasattr(field, 'blank') and field.blank:
                    details.append("BLANK")
                if hasattr(field, 'unique') and field.unique:
                    details.append("UNIQUE")

                details_str = ", ".join(details)
                
                # Výpis samotného řádku s polem
                self.stdout.write(f"  {field_name:<23} | {field_type:<25} | {details_str}")

        self.stdout.write(self.style.NOTICE("\n" + "="*80))
        self.stdout.write(self.style.NOTICE(f"✅ VÝPIS DOKONČEN. Celkem nalezeno {len(all_models)} modelů."))
        self.stdout.write(self.style.NOTICE("="*80 + "\n"))