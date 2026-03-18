from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('', views.render_homepage, name="homepage"),
    path('countries/', views.countries_list, name="countries"),
    path('territories/', views.territories_list, name="territories"),
    path('historical/', views.historical_list, name="historical"),
    path('country/<str:cca3>/', views.country_detail, name="country_detail"),
    path('flags/', views.flags_gallery, name="flags_gallery"),
    path('flag/<slug:slug>/', views.flag_detail, name="flag_detail"),
    path('about/', views.render_about, name="about"),
]
