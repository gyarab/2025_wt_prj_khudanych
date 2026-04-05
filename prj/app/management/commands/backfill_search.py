from django.core.management.base import BaseCommand

from app.models import Country, FlagCollection


class Command(BaseCommand):
    help = 'Backfill normalized search_name values for Country and FlagCollection records.'

    def handle(self, *args, **options):
        country_count = 0
        flag_count = 0

        for country in Country.objects.all().iterator(chunk_size=500):
            country.save()
            country_count += 1

        for flag in FlagCollection.objects.all().iterator(chunk_size=500):
            flag.save()
            flag_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Backfilled search_name for {country_count} countries and {flag_count} flag collections.'
        ))