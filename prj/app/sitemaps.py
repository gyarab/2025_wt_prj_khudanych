from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import FlagCollection

class FlagCollectionSitemap(Sitemap):
    i18n = True
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return FlagCollection.objects.all()

    def lastmod(self, obj):
        return obj.created_at

class StaticViewSitemap(Sitemap):
    i18n = True
    priority = 1.0
    changefreq = 'daily'

    def items(self):
        return ['homepage', 'countries', 'territories', 'historical', 'flags_gallery', 'about']

    def location(self, item):
        return reverse(item)
