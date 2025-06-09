from django.db import models
from django.utils import timezone

class Customer(models.Model): #客戶資料
    national_id = models.CharField(max_length=20, unique=True)  # 身分證號
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    has_luggage = models.BooleanField(default=False)  # 是否寄放行李

    def __str__(self):
        return f"{self.name} ({self.national_id})"


class RoomType(models.Model):  #房型資料
    code = models.CharField(max_length=10, primary_key=True)  # 房型編號
    name = models.CharField(max_length=50)  # 房型

    def __str__(self):
        return self.name


class Promotion(models.Model):  #促銷資料
    code = models.CharField(max_length=20, primary_key=True)  # 促銷編號
    name = models.CharField(max_length=100)
    room_type = models.OneToOneField(RoomType, on_delete=models.CASCADE)
    discount = models.DecimalField(max_digits=5, decimal_places=2)
    start_date = models.DateField(null=True, blank=True)  # 促銷開始日期
    end_date = models.DateField(null=True, blank=True)    # 促銷結束日期
    description = models.TextField(blank=True)            # 促銷描述
    is_active = models.BooleanField(default=True)        # 是否啟用

    def __str__(self):
        return self.name

    def is_valid(self):
        """檢查促銷是否在有效期內"""
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.start_date and self.end_date:
            return self.start_date <= today <= self.end_date
        return True


class Room(models.Model):  #房間資料
    room_number = models.CharField(max_length=10, primary_key=True)  # 房號
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20) #目前狀態(空房，使用中，已被預約等...
    promotion = models.ForeignKey(  #促銷資料
        Promotion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rooms"
    )

    def __str__(self):
        return f"Room {self.room_number}"


class Reservation(models.Model):  #預約資料
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    checkin_date = models.DateField()
    checkout_date = models.DateField()
    nights = models.PositiveIntegerField()
    guest_count = models.PositiveIntegerField(default=1)  # 新增欄位：預約人數

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['customer', 'room', 'checkin_date'], name='unique_reservation')
        ]

    def __str__(self):
        return f"Reservation for {self.customer} in {self.room}"


class CheckIn(models.Model): #入住資料
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE) #客戶
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    guest_count = models.PositiveIntegerField() #人數
    checkin_time = models.DateTimeField()
    checkout_time = models.DateTimeField(null=True, blank=True)  # <--- 修改這一行

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['customer', 'room', 'checkin_time'], name='unique_checkin')
        ]

    def __str__(self):
        return f"Check-in: {self.customer} -> {self.room}"

