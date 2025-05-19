from django.contrib import admin
from .models import Customer, RoomType, Promotion, Room, Reservation, CheckIn
# Register your models here.

admin.site.register(Customer)
admin.site.register(RoomType)
admin.site.register(Promotion)
admin.site.register(Room)
admin.site.register(Reservation)
admin.site.register(CheckIn)
