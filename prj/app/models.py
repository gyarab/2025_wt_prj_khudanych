from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Region(models.Model):
    """Geographic region/continent"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Country(models.Model):
    """Country or territory with detailed information"""
    # Basic Info
    name_common = models.CharField(max_length=200, db_index=True)
    name_official = models.CharField(max_length=200)
    cca2 = models.CharField(max_length=2, unique=True)  # ISO 3166-1 alpha-2
    cca3 = models.CharField(max_length=3, unique=True)  # ISO 3166-1 alpha-3
    
    # Geographic Info
    capital = models.CharField(max_length=200, blank=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, related_name='countries')
    subregion = models.CharField(max_length=100, blank=True)
    
    # Population and Area
    population = models.BigIntegerField(default=0)
    area = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Flags
    flag_svg = models.URLField(max_length=500, blank=True)
    flag_png = models.URLField(max_length=500, blank=True)
    flag_emoji = models.CharField(max_length=10, blank=True)
    coat_of_arms_svg = models.URLField(max_length=500, blank=True)
    coat_of_arms_png = models.URLField(max_length=500, blank=True)
    
    # Additional Info
    currencies = models.JSONField(default=dict, blank=True)
    languages = models.JSONField(default=dict, blank=True)
    timezones = models.JSONField(default=list, blank=True)
    continents = models.JSONField(default=list, blank=True)
    borders = models.JSONField(default=list, blank=True)  # List of country codes
    
    # Independence
    independent = models.BooleanField(default=True)
    un_member = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name_common']
        verbose_name_plural = 'Countries'
        indexes = [
            models.Index(fields=['name_common']),
            models.Index(fields=['region']),
            models.Index(fields=['population']),
        ]
    
    def __str__(self):
        return f"{self.flag_emoji} {self.name_common}"
    
    @property
    def currencies_display(self):
        """Return formatted currency string"""
        if not self.currencies:
            return "N/A"
        return ", ".join([f"{v.get('name', '')} ({k})" for k, v in self.currencies.items()])
    
    @property
    def languages_display(self):
        """Return formatted languages string"""
        if not self.languages:
            return "N/A"
        return ", ".join(self.languages.values())

class FlagCollection(models.Model):
    """Additional flag collection for territories, historical flags, etc."""
    CATEGORY_CHOICES = [
        ('territory', 'Territory'),
        ('historical', 'Historical'),
        ('state', 'State/Province'),
        ('city', 'City / Municipality'),
        ('international', 'International Organization'),
        ('region', 'Region / Subdivision'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)

    flag_image = models.URLField(max_length=500)
    wikidata_id = models.CharField(max_length=20, blank=True, db_index=True,
                                   help_text='Wikidata QID for deduplication')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL,
                                null=True, blank=True,
                                related_name='additional_flags')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
