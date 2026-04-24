from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView
from django.contrib.sitemaps.views import sitemap
from app import views as app_views
from app.sitemaps import CountrySitemap, FlagSitemap, StaticViewSitemap
from django.views.static import serve

sitemaps = {
    'static': StaticViewSitemap,
    'countries': CountrySitemap,
    'flags': FlagSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url='/static/app/logo.svg')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', app_views.robots_txt),
    
    # Přihlašování je teď jazykově neutrální!
    path('accounts/', include('allauth.urls')), 
]

urlpatterns += i18n_patterns(
    path('', include('app.urls')),
)

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)