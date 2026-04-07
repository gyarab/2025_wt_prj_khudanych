"""
Management command to populate owner relationships for territories.
This is a one-time data migration to establish the hierarchical relationship
between sovereign states and their dependent territories.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from app.models import Country


# Territory ownership mapping from eligibility.py
TERRITORY_OWNER_BY_CCA3 = {
    # United Kingdom
    'AIA': 'GBR', 'BMU': 'GBR', 'CYM': 'GBR', 'FLK': 'GBR', 'GGY': 'GBR', 'GIB': 'GBR',
    'IMN': 'GBR', 'JEY': 'GBR', 'MSR': 'GBR', 'PCN': 'GBR', 'SGS': 'GBR', 'TCA': 'GBR', 'VGB': 'GBR',
    # France
    'BLM': 'FRA', 'GUF': 'FRA', 'GLP': 'FRA', 'MAF': 'FRA', 'MTQ': 'FRA', 'MYT': 'FRA',
    'NCL': 'FRA', 'PYF': 'FRA', 'REU': 'FRA', 'SPM': 'FRA', 'WLF': 'FRA',
    # United States
    'ASM': 'USA', 'GUM': 'USA', 'MNP': 'USA', 'PRI': 'USA', 'UMI': 'USA', 'VIR': 'USA',
    # Netherlands
    'ABW': 'NLD', 'CUW': 'NLD', 'SXM': 'NLD', 'ANT': 'NLD',
    # China
    'HKG': 'CHN', 'MAC': 'CHN',
    # Denmark
    'FRO': 'DNK', 'GRL': 'DNK',
    # New Zealand
    'COK': 'NZL', 'NIU': 'NZL', 'TKL': 'NZL',
    # Australia
    'CXR': 'AUS', 'CCK': 'AUS', 'NFK': 'AUS',
    # Morocco
    'ESH': 'MAR',
}


class Command(BaseCommand):
    help = 'Populate owner relationships for territories from hardcoded mapping'

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
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        with transaction.atomic():
            for territory_cca3, owner_cca3 in TERRITORY_OWNER_BY_CCA3.items():
                try:
                    # Find the territory
                    territory = Country.objects.filter(cca3=territory_cca3).first()
                    if not territory:
                        self.stdout.write(
                            self.style.WARNING(f'Territory {territory_cca3} not found in database')
                        )
                        skipped_count += 1
                        continue
                    
                    # Find the owner country
                    owner = Country.objects.filter(cca3=owner_cca3, status='sovereign').first()
                    if not owner:
                        self.stdout.write(
                            self.style.ERROR(f'Owner {owner_cca3} not found or not sovereign for {territory_cca3}')
                        )
                        error_count += 1
                        continue
                    
                    # Check if already set
                    if territory.owner == owner:
                        self.stdout.write(f'  {territory_cca3} -> {owner_cca3} (already set)')
                        skipped_count += 1
                        continue
                    
                    # Update the relationship
                    if not dry_run:
                        territory.owner = owner
                        territory.save(update_fields=['owner'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ {territory.name_common} ({territory_cca3}) -> {owner.name_common} ({owner_cca3})'
                        )
                    )
                    updated_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing {territory_cca3}: {str(e)}')
                    )
                    error_count += 1
            
            if dry_run:
                # Rollback transaction in dry-run mode
                transaction.set_rollback(True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SUMMARY:'))
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Errors: {error_count}')
        self.stdout.write(f'  Total processed: {len(TERRITORY_OWNER_BY_CCA3)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Territory ownership relationships populated successfully!'))
