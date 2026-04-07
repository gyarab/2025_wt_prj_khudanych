"""
Management command to update status field for dependent territories.
This ensures territories have status='territory' instead of status='sovereign'.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import Country


class Command(BaseCommand):
    help = 'Update status field for dependent territories (independent=False) to status=territory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Find all countries that are dependent (independent=False) but have status='sovereign'
        territories_to_update = Country.objects.filter(
            independent=False,
            status='sovereign'
        ).exclude(
            # Exclude Antarctica and other special cases that should remain sovereign
            cca3__in=['ATA', 'BVT', 'IOT', 'BES', 'HMD', 'ATF', 'SJM']
        )
        
        total_count = territories_to_update.count()
        self.stdout.write(f'Found {total_count} territories to update')
        
        with transaction.atomic():
            for territory in territories_to_update:
                old_status = territory.status
                if not dry_run:
                    territory.status = 'territory'
                    territory.save(update_fields=['status'])
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {territory.name_common} ({territory.cca3}): {old_status} -> territory'
                    )
                )
            
            if dry_run:
                transaction.set_rollback(True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS(f'Total updated: {total_count}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Territory status updated successfully!'))
