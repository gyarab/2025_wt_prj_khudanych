from django.core.management.base import BaseCommand

from app.models import FlagCollection
from app.views.text_utils import normalize_query


class Command(BaseCommand):
    help = "Backfill normalized search_name for all FlagCollection records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of rows per iterator and bulk update batch (default: 1000).",
        )

    def handle(self, *args, **options):
        batch_size = max(1, int(options["batch_size"]))

        qs = FlagCollection.objects.only("id", "name", "name_cs", "name_de", "search_name").order_by("id")
        total = qs.count()

        self.stdout.write(self.style.NOTICE(f"Starting flag search_name backfill for {total} records..."))

        to_update = []
        scanned = 0
        updated = 0

        for flag in qs.iterator(chunk_size=batch_size):
            scanned += 1

            parts = [
                normalize_query(flag.name or ""),
                normalize_query(flag.name_cs or ""),
                normalize_query(flag.name_de or ""),
            ]
            new_search_name = " ".join(part for part in parts if part)

            if flag.search_name != new_search_name:
                flag.search_name = new_search_name
                to_update.append(flag)

            if len(to_update) >= batch_size:
                FlagCollection.objects.bulk_update(to_update, ["search_name"], batch_size=batch_size)
                updated += len(to_update)
                to_update.clear()

            if scanned % batch_size == 0 or scanned == total:
                self.stdout.write(f"Processed {scanned}/{total} records; updated {updated}.")

        if to_update:
            FlagCollection.objects.bulk_update(to_update, ["search_name"], batch_size=batch_size)
            updated += len(to_update)

        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated} of {total} FlagCollection records."))
