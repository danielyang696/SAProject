'''
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Room, Customer, CheckIn


def room_detail(request, room_number):
    room = get_object_or_404(Room, room_number=room_number)
    checkin = CheckIn.objects.filter(room=room).first()
    context = {
        'room': room,
        'checkin': checkin,
    }
    return render(request, 'room.html', context)

def checkin(request, room_number):
    room = get_object_or_404(Room, room_number=room_number)
    if request.method == "POST":
        national_id = request.POST.get('national_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        guest_count = int(request.POST.get('guest_count'))

        # 取得或建立客戶
        customer, created = Customer.objects.get_or_create(
            national_id=national_id,
            defaults={'name': name, 'phone': phone}
        )
        if not created:
            customer.name = name
            customer.phone = phone
            customer.save()

        # 建立入住資料
        CheckIn.objects.create(
            customer=customer,
            room=room,
            guest_count=guest_count,
            checkin_time=timezone.now(),
            checkout_time=None
        )
        # 更新房間狀態
        room.status = "使用中"
        room.save()
        return redirect('room_detail', room_number=room_number)
    return redirect('room_detail', room_number=room_number)

def checkout(request, checkin_id):
    checkin = get_object_or_404(CheckIn, id=checkin_id)
    room = checkin.room
    customer = checkin.customer

    if request.method == "POST":
        # 更新房間狀態
        room.status = "空房"
        room.save()

        # 刪除 checkin 資料
        checkin.delete()

        # 若客戶無其他 checkin，則刪除客戶
        if not CheckIn.objects.filter(customer=customer).exists():
            customer.delete()
        return redirect('room_detail', room_number=room.room_number)
    return redirect('room_detail', room_number=room.room_number)
'''

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from .models import Room, Customer, CheckIn
from django.utils import timezone

def dashboard(request):
    rooms = Room.objects.all().order_by('room_number')
    # 取得所有唯一樓層（假設房號第一碼為樓層）
    floors = sorted(set(room.room_number[0] for room in rooms))
    return render(request, 'homepage.html', {'rooms': rooms, 'floors': floors})

@csrf_exempt
def checkin(request, room_number):
    room = get_object_or_404(Room, room_number=room_number)
    if request.method == 'POST':
        national_id = request.POST.get('national_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        guest_count = int(request.POST.get('guest_count'))
        has_luggage = request.POST.get('has_luggage') == 'true'

        customer, created = Customer.objects.get_or_create(
            national_id=national_id,
            defaults={'name': name, 'phone': phone, 'has_luggage': has_luggage}
        )
        if not created:
            customer.name = name
            customer.phone = phone
            customer.has_luggage = has_luggage
            customer.save()

        CheckIn.objects.create(
            customer=customer,
            room=room,
            guest_count=guest_count,
            checkin_time=timezone.now(),
            checkout_time=None
        )
        room.status = '使用中'
        room.save()
        return redirect('dashboard')
    return redirect('dashboard')

@csrf_exempt
def checkout(request, room_number):
    room = get_object_or_404(Room, room_number=room_number)
    # 找到這個房間目前的 checkin 資料
    checkin = CheckIn.objects.filter(room=room).first()
    if checkin:
        customer = checkin.customer
        # 更新房間狀態
        room.status = "空房"
        room.save()
        # 刪除 checkin 資料
        checkin.delete()
        # 如果這個客戶沒有其他 checkin，則刪除客戶資料
        if not CheckIn.objects.filter(customer=customer).exists():
            customer.delete()
    return redirect('dashboard')