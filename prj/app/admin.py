from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Country, Region, FlagCollection, Profile

# --- USER & PROFILE SECTION ---
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profiles'

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'nickname_change_count', 'last_nickname_change')
    search_fields = ('user__username', 'user__email', 'display_name', 'unique_id')
    readonly_fields = ('unique_id',)
    fieldsets = (
        (None, {
            'fields': ('user', 'unique_id', 'display_name', 'profile_picture')
        }),
        ('Nickname Change History', {
            'fields': ('nickname_change_count', 'last_nickname_change'),
            'classes': ('collapse',)
        }),
    )

# --- GEOGRAPHIC SECTION ---
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

# --- THE CLEANING MACHINE (FlagCollection) ---
@admin.register(FlagCollection)
class FlagCollectionAdmin(admin.ModelAdmin):
    # 'list_editable' ti dovolí měnit checkboxy přímo v seznamu bez rozkliknutí!
    list_display = ['name', 'category', 'country', 'is_verified', 'is_public', 'wikidata_id']
    list_editable = ['is_verified', 'is_public'] 
    list_filter = ['category', 'is_verified', 'is_public', 'country']
    search_fields = ['name', 'wikidata_id']
    
    # Hromadné akce pro rychlé mazání/schovávání
    actions = ['mark_as_verified', 'hide_from_public', 'show_on_public']

    @admin.action(description='Verify selected flags')
    def mark_as_verified(self, request, queryset):
        queryset.update(is_verified=True)
        self.stdout.write(f"Successfully verified {queryset.count()} flags.")

    @admin.action(description='Hide selected flags from website')
    def hide_from_public(self, request, queryset):
        queryset.update(is_public=False)

    @admin.action(description='Show selected flags on website')
    def show_on_public(self, request, queryset):
        queryset.update(is_public=True)