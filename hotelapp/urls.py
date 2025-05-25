from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('checkin/<str:room_number>/', views.checkin, name='checkin'),
    path('checkout/<str:room_number>/', views.checkout, name='checkout'),
]