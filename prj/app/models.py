import uuid
import unicodedata
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from datetime import timedelta

# Import naší zkompilované Rust knihovny pro zrychlení operací
import flag_search_core


def _normalize_search_value(value):
    if not isinstance(value, str):
        return ''
    return unicodedata.normalize('NFD', value).encode('ascii', 'ignore').decode('utf-8').lower()

class Profile(models.Model):
    """Extended user profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    display_name = models.CharField(max_length=255, blank=True, verbose_name=_("Display Name"))
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True, verbose_name=_("Profile Picture"))
    
    # Nickname change tracking
    nickname_change_count = models.PositiveIntegerField(default=0, verbose_name=_("Nickname Change Count"))
    last_nickname_change = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Nickname Change"))

    def __str__(self):
        return f"{self.user.username}'s profile"

    def clean(self):
        super().clean()
        if self.pk:
            old_profile = Profile.objects.get(pk=self.pk)
            if self.display_name != old_profile.display_name:
                now = timezone.now()
                # Cooldown check: 7 days
                if self.last_nickname_change:
                    cooldown_period = timedelta(days=7)
                    if now < self.last_nickname_change + cooldown_period:
                        days_left = (self.last_nickname_change + cooldown_period - now).days
                        raise ValidationError({
                            'display_name': _("Please wait %(days)s more day(s) before changing your nickname again.") % {'days': days_left + 1}
                        })

                    # Monthly limit check: 2 times per month
                    if self.last_nickname_change.month == now.month and self.last_nickname_change.year == now.year:
                        if self.nickname_change_count >= 2:
                            raise ValidationError({
                                'display_name': _("You have already changed your nickname twice this month. Please try again next month.")
                            })

    def save(self, *args, **kwargs):
        if self.pk:
            old_profile = Profile.objects.get(pk=self.pk)
            if self.display_name != old_profile.display_name:
                now = timezone.now()
                if self.last_nickname_change and (self.last_nickname_change.month != now.month or self.last_nickname_change.year != now.year):
                    self.nickname_change_count = 1
                else:
                    self.nickname_change_count += 1
                self.last_nickname_change = now
        super().save(*args, **kwargs)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create a profile for new users"""
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure profile is saved when user is saved"""
    instance.profile.save()

class Region(models.Model):
    """Geographic region/continent"""
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(max_length=100, unique=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
    
    def __str__(self):
        return self.name

class Country(models.Model):
    """Country or territory with detailed information"""
    # Basic Info
    name_common = models.CharField(max_length=200, db_index=True, verbose_name=_("Common Name"))
    name_official = models.CharField(max_length=200, verbose_name=_("Official Name"))
    search_name = models.CharField(max_length=255, blank=True, default='', db_index=True)
    cca2 = models.CharField(max_length=2, unique=True, verbose_name=_("ISO Alpha-2"))
    cca3 = models.CharField(max_length=3, unique=True, verbose_name=_("ISO Alpha-3"))
    
    # Geographic Info
    capital = models.CharField(max_length=200, blank=True, verbose_name=_("Capital"))
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, related_name='countries', verbose_name=_("Region"))
    subregion = models.CharField(max_length=100, blank=True, verbose_name=_("Subregion"))
    
    # Population and Area
    population = models.BigIntegerField(default=0, verbose_name=_("Population"))
    area_km2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name=_("Area"))
    
    # Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name=_("Latitude"))
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name=_("Longitude"))
    
    # Flags
    flag_svg = models.URLField(max_length=500, blank=True, verbose_name=_("Flag SVG"))
    flag_png = models.URLField(max_length=500, blank=True, verbose_name=_("Flag PNG"))
    flag_emoji = models.CharField(max_length=10, blank=True, verbose_name=_("Flag Emoji"))
    coat_of_arms_svg = models.URLField(max_length=500, blank=True, verbose_name=_("Coat of Arms SVG"))
    coat_of_arms_png = models.URLField(max_length=500, blank=True, verbose_name=_("Coat of Arms PNG"))
    
    # Additional Info
    currencies = models.JSONField(default=dict, blank=True, verbose_name=_("Currencies"))
    languages = models.JSONField(default=dict, blank=True, verbose_name=_("Languages"))
    timezones = models.JSONField(default=list, blank=True, verbose_name=_("Timezones"))
    continents = models.JSONField(default=list, blank=True, verbose_name=_("Continents"))
    borders = models.JSONField(default=list, blank=True, verbose_name=_("Borders"))
    
    # Independence
    independent = models.BooleanField(default=True, verbose_name=_("Independent"))
    un_member = models.BooleanField(default=False, verbose_name=_("UN Member"))
    
    STATUS_CHOICES = [
        ('sovereign', _('Sovereign State')),
        ('territory', _('Territory')),
        ('historical', _('Historical')),
        ('other', _('Other')),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sovereign', db_index=True, verbose_name=_("Status"))
    
    # Hierarchical relationship for territories
    owner = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependencies',
        limit_choices_to={'status': 'sovereign'},
        verbose_name=_("Owner Country")
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        ordering = ['name_common']
        verbose_name = _("Country")
        verbose_name_plural = _("Countries")
        indexes = [
            models.Index(fields=['name_common']),
            models.Index(fields=['region']),
            models.Index(fields=['population']),
        ]
    
    def __str__(self):
        return f"{self.flag_emoji} {self.name_common}"

    def save(self, *args, **kwargs):
        self.search_name = _normalize_search_value(self.name_common)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('country_detail', kwargs={'cca3': self.cca3})
    
    @property
    def currencies_display(self):
        """Return formatted currency string"""
        if not self.currencies or not isinstance(self.currencies, dict):
            return "N/A"
        return ", ".join([f"{v.get('name', '') if isinstance(v, dict) else v} ({k})" for k, v in self.currencies.items()])
    
    @property
    def languages_display(self):
        """Return formatted languages string"""
        if not self.languages or not isinstance(self.languages, dict):
            return "N/A"
        return ", ".join(self.languages.values())

class FlagCollection(models.Model):
    """Additional flag collection for territories, historical flags, etc."""
    CATEGORY_VALUES = (
        'country',
        'dependency',
        'city',
        'region',
        'historical',
        'international',
    )

    CATEGORY_CHOICES = [
        ('country', _('Country')),
        ('dependency', _('Dependency')),
        ('city', _('Obec / Město')),
        ('region', _('Region / Subdivision')),
        ('historical', _('Historical')),
        ('international', _('International Organization')),
    ]

    name = models.CharField(max_length=200, verbose_name=_("Name"))
    search_name = models.CharField(max_length=255, blank=True, default='', db_index=True)
    name_cs = models.CharField(max_length=200, blank=True, default='', verbose_name=_("Name (Czech)"))
    name_de = models.CharField(max_length=200, blank=True, default='', verbose_name=_("Name (German)"))
    slug = models.SlugField(max_length=255, unique=True, blank=True, verbose_name=_("Slug"))
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, verbose_name=_("Category"))
    description = models.JSONField(default=dict, blank=True, verbose_name=_("Description"))

    flag_image = models.URLField(max_length=500, verbose_name=_("Flag Image URL"))
    image_file = models.FileField(upload_to='flags/', blank=True, null=True,
                                 help_text=_('Local copy of the flag image'), verbose_name=_("Flag Image File"))
    population = models.IntegerField(null=True, blank=True, verbose_name=_("Population"))
    area_km2 = models.FloatField(null=True, blank=True, verbose_name=_("Area (km²)"))
    latitude = models.FloatField(null=True, blank=True, verbose_name=_("Latitude"))
    longitude = models.FloatField(null=True, blank=True, verbose_name=_("Longitude"))
    wikidata_id = models.CharField(max_length=20, blank=True, null=True, unique=True,
                                   help_text=_('Wikidata QID for deduplication'), verbose_name=_("Wikidata ID"))
    country = models.ForeignKey(Country, on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='additional_flags', verbose_name=_("Country"))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    is_verified = models.BooleanField(default=False, help_text=_("Checked by human or AI"), verbose_name=_("Is Verified"))
    is_public = models.BooleanField(default=True, help_text=_("Visible on the website"), verbose_name=_("Is Public"))

    class Meta:
        ordering = ['name']
        verbose_name = _("Flag Collection")
        verbose_name_plural = _("Flag Collections")
        indexes = [
            models.Index(fields=['category']),
        ]
        constraints = [
            models.CheckConstraint(
                name='flagcollection_category_valid',
                condition=models.Q(category__in=(
                    'country',
                    'dependency',
                    'city',
                    'region',
                    'historical',
                    'international',
                )),
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('flag_detail', kwargs={'category': self.category, 'slug': self.slug})

    @property
    def localized_name(self):
        cur_lang = (translation.get_language() or '').split('-')[0]
        if cur_lang == 'cs' and self.name_cs:
            return self.name_cs
        if cur_lang == 'de' and self.name_de:
            return self.name_de
        return self.name

    def save(self, *args, **kwargs):
        self.search_name = _normalize_search_value(self.name)

        # Keep country binding idempotent: consume ISO3 hints from structured description.
        description = self.description if isinstance(self.description, dict) else {}
        parent_iso3 = description.get('parent_country_iso3')
        if isinstance(parent_iso3, str):
            parent_iso3 = parent_iso3.strip().upper()
            if len(parent_iso3) == 3:
                parent_country = Country.objects.filter(cca3=parent_iso3).first()
                if parent_country:
                    self.country = parent_country

        if not self.slug:
            from django.utils.text import slugify
            
            en_label = description.get('label_en')
            
            # Předání výpočetní zátěže (regex a kontrola) do Rustu
            base_name = flag_search_core.get_slug_base(self.name, en_label)
            self.slug = slugify(f"{base_name}-{self.wikidata_id or ''}")
            
        super().save(*args, **kwargs)