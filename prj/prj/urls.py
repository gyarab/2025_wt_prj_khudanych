from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from app.sitemaps import FlagCollectionSitemap, StaticViewSitemap
from django.views.static import serve

sitemaps = {
    'static': StaticViewSitemap,
    'flags': FlagCollectionSitemap,
}

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url='/static/app/logo.svg')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt),
    
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