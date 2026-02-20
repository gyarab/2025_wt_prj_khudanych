from django.contrib import admin
from .models import Region, Country, FlagCollection

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['flag_emoji', 'name_common', 'capital', 'region', 'population', 'independent']
    list_filter = ['region', 'independent', 'un_member']
    search_fields = ['name_common', 'name_official', 'capital', 'cca2', 'cca3']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_common', 'name_official', 'cca2', 'cca3')
        }),
        ('Geographic Information', {
            'fields': ('capital', 'region', 'subregion', 'latitude', 'longitude', 'area', 'continents')
        }),
        ('Flags & Symbols', {
            'fields': ('flag_emoji', 'flag_svg', 'flag_png', 'coat_of_arms_svg', 'coat_of_arms_png')
        }),
        ('Demographics', {
            'fields': ('population', 'currencies', 'languages', 'timezones')
        }),
        ('Political Information', {
            'fields': ('independent', 'un_member', 'borders')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(FlagCollection)
class FlagCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'country']
    list_filter = ['category']
    search_fields = ['name', 'description']
