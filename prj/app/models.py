import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

class Profile(models.Model):
    """Extended user profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    display_name = models.CharField(max_length=255, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Nickname change tracking
    nickname_change_count = models.PositiveIntegerField(default=0)
    last_nickname_change = models.DateTimeField(null=True, blank=True)

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
                            'display_name': f"Please wait {days_left + 1} more day(s) before changing your nickname again."
                        })

                    # Monthly limit check: 2 times per month
                    if self.last_nickname_change.month == now.month and self.last_nickname_change.year == now.year:
                        if self.nickname_change_count >= 2:
                            raise ValidationError({
                                'display_name': "You have already changed your nickname twice this month. Please try again next month."
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
    
    STATUS_CHOICES = [
        ('sovereign', 'Sovereign State'),
        ('territory', 'Territory'),
        ('historical', 'Historical'),
        ('other', 'Other'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sovereign', db_index=True)

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
    description = models.JSONField(default=dict, blank=True)

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
