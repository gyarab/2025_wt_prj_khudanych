from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from app.models import FlagCollection


class Command(BaseCommand):
    help = (
        "Re-categorize orphan dependency flags (category='dependency' with no linked country) "
        "to category='micronation'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply updates. Without this flag, command runs in dry-run mode.",
        )
        parser.add_argument(
            "--from-category",
            default="dependency",
            help="Source category to clean (default: dependency).",
        )
        parser.add_argument(
            "--to-category",
            default="micronation",
            help="Target category for recategorization (default: micronation).",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        from_category = options["from_category"].strip().lower()
        to_category = options["to_category"].strip().lower()

        valid_categories = set(FlagCollection.CATEGORY_VALUES)
        if from_category not in valid_categories:
            raise CommandError(
                f"Invalid --from-category '{from_category}'. Allowed values: {sorted(valid_categories)}"
            )
        if to_category not in valid_categories:
            raise CommandError(
                f"Invalid --to-category '{to_category}'. Allowed values: {sorted(valid_categories)}"
            )
        if from_category == to_category:
            raise CommandError("--from-category and --to-category must be different.")

        orphan_qs = FlagCollection.objects.filter(
            category=from_category,
            country__isnull=True,
        ).order_by("id")

        orphan_count = orphan_qs.count()

        self.stdout.write(self.style.WARNING("\n=== Micronation Cleanup ==="))
        self.stdout.write(
            f"Found orphan flags: {orphan_count} "
            f"(category='{from_category}', country IS NULL)"
        )

        if orphan_count == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to update."))
            return

        sample_rows = list(orphan_qs.values("id", "name", "slug")[:50])
        self.stdout.write("Sample rows:")
        for row in sample_rows:
            self.stdout.write(f"  - ID {row['id']}: {row['name']} ({row['slug']})")

        if not apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run only. Re-run with --apply to execute updates."
                )
            )
            return

        try:
            with transaction.atomic():
                updated_count = orphan_qs.update(category=to_category)
        except IntegrityError as exc:
            raise CommandError(
                "Database constraint prevented update. Make sure migrations are applied "
                "and category check constraint includes the target category."
            ) from exc

        remaining_count = FlagCollection.objects.filter(
            category=from_category,
            country__isnull=True,
        ).count()

        self.stdout.write(self.style.SUCCESS("\nCleanup applied successfully."))
        self.stdout.write(f"Updated records: {updated_count}")
        self.stdout.write(f"Remaining orphan records in '{from_category}': {remaining_count}")
