# proxy/urls.py

from django.urls import path
from .views import create_room

urlpatterns = [
    path('create_room/', create_room, name='create_room'),
]
