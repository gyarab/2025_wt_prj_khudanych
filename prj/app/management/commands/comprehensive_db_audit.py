from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from app.models import Country, FlagCollection, Profile, Region


class Command(BaseCommand):
    help = "Comprehensive aggregate DB audit for schema/data health checks"

    def _country_label(self, country):
        return {
            "id": country.id,
            "name_common": country.name_common,
            "cca3": country.cca3,
        }

    def _flag_label(self, flag):
        return {
            "id": flag.id,
            "name": flag.name,
            "category": flag.category,
            "country_id": flag.country_id,
        }

    def handle(self, *args, **options):
        self.stdout.write("=== JEF Comprehensive DB Audit ===")

        # 1) Volume
        self.stdout.write("\n[1] Volume")
        self.stdout.write(f"- Regions: {Region.objects.count()}")
        self.stdout.write(f"- Countries: {Country.objects.count()}")
        self.stdout.write(f"- FlagCollection: {FlagCollection.objects.count()}")
        self.stdout.write(f"- Profiles: {Profile.objects.count()}")
        self.stdout.write(f"- Users: {User.objects.count()}")

        # 2) Referential integrity / structural contradictions
        self.stdout.write("\n[2] Referential Integrity & Nulls")

        flags_country_null_qs = FlagCollection.objects.filter(country__isnull=True)
        flags_country_null_count = flags_country_null_qs.count()
        self.stdout.write(f"- FlagCollection with country=NULL: {flags_country_null_count}")

        self.stdout.write("- country=NULL grouped by category (count + 1 sample):")
        grouped = (
            flags_country_null_qs.values("category")
            .annotate(total=Count("id"))
            .order_by("-total", "category")
        )
        if grouped:
            for row in grouped:
                sample = (
                    FlagCollection.objects.filter(
                        country__isnull=True,
                        category=row["category"],
                    )
                    .only("id", "name", "category", "country")
                    .order_by("id")
                    .first()
                )
                self.stdout.write(
                    f"  - {row['category']}: {row['total']} | sample={self._flag_label(sample) if sample else None}"
                )
        else:
            self.stdout.write("  - none")

        countries_region_null_count = Country.objects.filter(region__isnull=True).count()
        self.stdout.write(f"- Country with region=NULL: {countries_region_null_count}")

        independent_false_owner_null_qs = Country.objects.filter(
            independent=False,
            owner__isnull=True,
        )
        self.stdout.write(
            "- Country with independent=False AND owner=NULL: "
            f"{independent_false_owner_null_qs.count()}"
        )
        contradiction_examples = list(independent_false_owner_null_qs.order_by("id")[:2])
        if contradiction_examples:
            self.stdout.write(
                "  samples="
                + str([self._country_label(country) for country in contradiction_examples])
            )

        # 3) Data completeness
        self.stdout.write("\n[3] Data Completeness")
        missing_flag_image = FlagCollection.objects.filter(
            Q(flag_image__isnull=True) | Q(flag_image="")
        ).count()
        missing_image_file = FlagCollection.objects.filter(image_file__isnull=True).count()
        missing_both_images = FlagCollection.objects.filter(
            Q(flag_image__isnull=True) | Q(flag_image=""),
            image_file__isnull=True,
        ).count()
        self.stdout.write(f"- FlagCollection missing flag_image URL: {missing_flag_image}")
        self.stdout.write(f"- FlagCollection missing image_file: {missing_image_file}")
        self.stdout.write(f"- FlagCollection missing BOTH image sources: {missing_both_images}")

        country_missing_cca3_qs = Country.objects.filter(
            Q(cca3__isnull=True) | Q(cca3="")
        )
        self.stdout.write(f"- Country missing cca3: {country_missing_cca3_qs.count()}")
        if country_missing_cca3_qs.exists():
            self.stdout.write(
                "  samples="
                + str([
                    self._country_label(country)
                    for country in country_missing_cca3_qs.order_by("id")[:2]
                ])
            )

        country_missing_capital_qs = Country.objects.filter(
            Q(capital__isnull=True) | Q(capital="")
        )
        self.stdout.write(f"- Country missing capital: {country_missing_capital_qs.count()}")
        if country_missing_capital_qs.exists():
            self.stdout.write(
                "  samples="
                + str([
                    self._country_label(country)
                    for country in country_missing_capital_qs.order_by("id")[:2]
                ])
            )

        # 4) Duplicates / overlap
        self.stdout.write("\n[4] Duplicates / Overlap")
        wikidata_collisions = list(
            FlagCollection.objects.exclude(wikidata_id__isnull=True)
            .exclude(wikidata_id="")
            .values("wikidata_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("-total", "wikidata_id")
        )
        self.stdout.write(f"- Wikidata ID collisions: {len(wikidata_collisions)}")
        if wikidata_collisions:
            first_collision = wikidata_collisions[0]
            sample_flags = list(
                FlagCollection.objects.filter(wikidata_id=first_collision["wikidata_id"])
                .only("id", "name", "category", "country")
                .order_by("id")[:2]
            )
            self.stdout.write(
                f"  sample_qid={first_collision['wikidata_id']}"
                f" count={first_collision['total']}"
                f" samples={[self._flag_label(flag) for flag in sample_flags]}"
            )

        duplicate_country_category = list(
            FlagCollection.objects.filter(country__isnull=False)
            .values("country_id", "category")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by("-total", "country_id", "category")
        )
        self.stdout.write(
            "- Duplicate (country, category) combinations in FlagCollection: "
            f"{len(duplicate_country_category)}"
        )
        if duplicate_country_category:
            first_dup = duplicate_country_category[0]
            sample_flags = list(
                FlagCollection.objects.filter(
                    country_id=first_dup["country_id"],
                    category=first_dup["category"],
                )
                .only("id", "name", "category", "country")
                .order_by("id")[:2]
            )
            self.stdout.write(
                f"  sample_country_id={first_dup['country_id']}"
                f" category={first_dup['category']}"
                f" count={first_dup['total']}"
                f" samples={[self._flag_label(flag) for flag in sample_flags]}"
            )

        self.stdout.write("\n=== End of Audit ===")