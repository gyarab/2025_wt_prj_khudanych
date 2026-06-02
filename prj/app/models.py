from django.db import models

class Country(models.Model):
    ENTITY_TYPES = [
        ('SOVEREIGN', 'Suverénní stát'),
        ('DEPENDENT', 'Závislé území'),
        ('DISPUTED', 'Sporné území'),
        ('ANTARCTIC', 'Antarktida'),
    ]

    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES, default='SOVEREIGN')
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
    
    is_independent = models.BooleanField(default=True)
    
    # Hodnocení pro frontendové řazení
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)

    @property
    def score(self):
        return self.upvotes - self.downvotes

    class Meta:
        verbose_name = "Country"
        verbose_name_plural = "Countries" 
        
        # Nastaví výchozí řazení pro celou aplikaci od A do Z podle běžného názvu
        # (Pro od Z do A: ["-name_common"])
        ordering = ["name_common"]

    def __str__(self):
        return self.name_common