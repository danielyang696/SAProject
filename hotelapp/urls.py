from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('checkin/<str:room_number>/', views.checkin, name='checkin'),
    path('checkout/<str:room_number>/', views.checkout, name='checkout'),
    path('add_reservation/', views.add_reservation, name='add_reservation'),  # 新增這行
    path('add_promotion/', views.add_promotion, name='add_promotion'),        # 如果有促銷功能也加
]