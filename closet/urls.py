from django.urls import path
from . import views

urlpatterns = [
    path("closet", views.closet, name="closet"),
    path("closet-feed/", views.closet_feed, name="closet-feed"),
    path("daily-outfit/", views.daily_outfit, name="daily-outfit"),
    path("weekly-outfits/", views.weekly_outfits, name="weekly-outfits"),
    path("update-outfits/", views.update_outfits, name="update-outfits"),
]
