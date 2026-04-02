from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('', views.render_homepage, name="homepage"),
    path('countries/', views.countries_list, name="countries"),
    path('countries/search-api/', views.countries_search_api, name="countries_search_api"),
    path('territories/', views.territories_list, name="territories"),
    path('territories/search-api/', views.territories_search_api, name='territories_search_api'),
    path('historical/', views.historical_list, name="historical"),
    path('historical/search-api/', views.historical_search_api, name='historical_search_api'),
    path('country/<str:cca3>/', views.country_detail, name="country_detail"),
    path('territory/<str:cca3>/', views.territory_detail, name="territory_detail"),
    path('flags/', views.flags_gallery, name="flags_gallery"),
    path('flags/search-api/', views.flags_search_api, name="flags_search_api"),
    path('flags/<str:category>/<slug:slug>/', views.flag_detail, name="flag_detail"),
    path('about/', views.render_about, name="about"),
]
