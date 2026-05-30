from django.db import models

class Country(models.Model):
    # cca3 použijeme jako primární klíč, v JSONu to bude hodnota "pk"
    cca3 = models.CharField(max_length=3, primary_key=True)
    cca2 = models.CharField(max_length=2, unique=True)
    
    name_common = models.CharField(max_length=150)
    name_official = models.CharField(max_length=200)
    capital = models.CharField(max_length=150, blank=True)
    
    region = models.CharField(max_length=100)
    subregion = models.CharField(max_length=100, blank=True)
    
    population = models.BigIntegerField()
    area_km2 = models.FloatField(null=True, blank=True)
    
    flag_svg = models.URLField(max_length=500)
    flag_png = models.URLField(max_length=500)
    coat_of_arms_svg = models.URLField(max_length=500, blank=True)
    
    is_independent = models.BooleanField(default=True)
    
    # Hodnocení pro frontendové řazení
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)

    def __str__(self):
        return self.name_common