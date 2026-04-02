from django.core.management.base import BaseCommand, CommandError

from app.models import FlagCollection


class Command(BaseCommand):
    help = "Safe cleanup utility for FlagCollection rows and physical image files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            type=str,
            help="Limit cleanup to a specific FlagCollection category",
        )
        parser.add_argument(
            "--delete-images",
            action="store_true",
            help="Delete physical files referenced by image_file",
        )
        parser.add_argument(
            "--clear-flagcollection",
            action="store_true",
            help="Delete selected FlagCollection database rows",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without making changes",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        if not options["delete_images"] and not options["clear_flagcollection"]:
            raise CommandError("Use at least one action: --delete-images and/or --clear-flagcollection")

        queryset = FlagCollection.objects.all()
        if options["category"]:
            queryset = queryset.filter(category=options["category"])

        total_rows = queryset.count()
        if total_rows == 0:
            self.stdout.write(self.style.WARNING("No matching FlagCollection rows found."))
            return

        image_candidates = [row for row in queryset if row.image_file and row.image_file.name]
        images_existing = [row for row in image_candidates if row.image_file.storage.exists(row.image_file.name)]

        self.stdout.write(self.style.WARNING("Cleanup plan:"))
        self.stdout.write(f"- Scope rows: {total_rows}")
        self.stdout.write(f"- Image refs: {len(image_candidates)}")
        self.stdout.write(f"- Existing image files: {len(images_existing)}")
        self.stdout.write(f"- Delete images: {bool(options['delete_images'])}")
        self.stdout.write(f"- Clear FlagCollection rows: {bool(options['clear_flagcollection'])}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No changes made."))
            return

        if not options["yes"]:
            confirm = input("Type 'yes' to continue: ").strip().lower()
            if confirm != "yes":
                self.stdout.write(self.style.ERROR("Cancelled. No changes made."))
                return

        deleted_files = 0
        if options["delete_images"]:
            for row in images_existing:
                try:
                    row.image_file.delete(save=False)
                    deleted_files += 1
                except Exception as exc:  # noqa: BLE001 - keep cleanup resilient
                    self.stderr.write(self.style.WARNING(f"Failed to delete image for '{row.name}': {exc}"))

        deleted_rows = 0
        if options["clear_flagcollection"]:
            deleted_rows, _ = queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup finished: deleted_files={deleted_files}, deleted_rows={deleted_rows}"
            )
        )
