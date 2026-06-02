from django.contrib import admin
from django.utils.html import format_html
from .models import Country

admin.site.site_header = "JEF Databáze Administrace"
admin.site.site_title = "JEF Admin"
admin.site.index_title = "Správa vlajkového projektu"

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    # Sloupce, které uvidíš v přehledné tabulce
    list_display = ["flag_thumb", "name_common", "cca3", "capital", "region", "is_independent", "upvotes", "downvotes"]
    
    # Kliknutím na název nebo miniaturu skočíš do editace
    list_display_links = ["flag_thumb", "name_common"]
    
    # Filtrační boční panel
    list_filter = ["region", "is_independent"]
    
    # Vyhledávací pole (hledá napříč názvy, kódy i hlavním městem)
    search_fields = ["name_common", "name_official", "cca3", "cca2", "capital"]
    
    # Rozdělení editačního formuláře do sekcí
    fieldsets = (
        ("Identifikace a názvy", {
            "fields": ("cca3", "cca2", "name_common", "name_official"),
        }),
        ("Geografie", {
            "fields": ("capital", "region", "subregion", "area_km2", "population"),
        }),
        ("Vizuální média", {
            "fields": ("flag_svg", "flag_png"),
        }),
        ("Politika a vztahy", {
            "fields": ["is_independent"],
        }),
        ("Statistiky", {
            "fields": ("upvotes", "downvotes"),
        }),
    )

    # Vlastní metoda pro vykreslení malé vlajky v tabulce
    @admin.display(description="Vlajka")
    def flag_thumb(self, obj):
        if not obj.flag_png:
            return "—"
        return format_html(
            '<img src="{}" style="height:25px; width:40px; object-fit:cover; border-radius:2px; border:1px solid #ccc;" />',
            obj.flag_png
        )