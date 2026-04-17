from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from app.models import Country, FlagCollection


class Command(BaseCommand):
    help = "Create a sample fixture with Czechia and 10-20 related flags."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=15,
            help="Number of related flags to include (10-20 recommended). Default: 15.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 10 or limit > 20:
            raise CommandError("--limit must be between 10 and 20.")

        country = Country.objects.filter(cca3="CZE").first()
        if not country:
            raise CommandError("Country with cca3='CZE' was not found.")

        flags_qs = FlagCollection.objects.filter(country=country).order_by("id")[:limit]
        flags = list(flags_qs)

        objects_to_serialize = [country, *flags]
        fixture_json = serializers.serialize("json", objects_to_serialize, indent=2)

        fixtures_dir = Path(settings.BASE_DIR).parent / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        output_path = fixtures_dir / "sample_europe.json"
        output_path.write_text(fixture_json + "\n", encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Fixture created: {output_path} (country=1, flags={len(flags)})"
            )
        )