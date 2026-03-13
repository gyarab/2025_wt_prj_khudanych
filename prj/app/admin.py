from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Country, Region, FlagCollection, Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profiles'

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

# Re-register UserAdmin
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
