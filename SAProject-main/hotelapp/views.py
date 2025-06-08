from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models import Room, Customer, CheckIn, Reservation, Promotion, RoomType
from django.utils import timezone
from django.http import JsonResponse

def dashboard(request):
    rooms = Room.objects.all().order_by('room_number')
    # 取得所有唯一樓層（假設房號第一碼為樓層）
    floors = sorted(set(room.room_number[0] for room in rooms))
    reservations = Reservation.objects.select_related('customer', 'room').all().order_by('-checkin_date')
    room_types = RoomType.objects.all()
    promotions = Promotion.objects.all().select_related('room_type')
    
    # 新增今天日期供模板使用
    today = timezone.now().date()
    
    return render(request, 'homepage.html', {
        'rooms': rooms,
        'floors': floors,
        'reservations': reservations,
        'room_types': room_types,
        'promotions': promotions,
        'today': today,
    })

@csrf_exempt
def checkin(request, room_number):
    room = get_object_or_404(Room, room_number=room_number)
    if request.method == 'POST':
        national_id = request.POST.get('national_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        guest_count = int(request.POST.get('guest_count'))
        has_luggage = request.POST.get('has_luggage') == 'true'

        today = timezone.now().date()
        reservation = Reservation.objects.filter(
            room=room,
            customer__national_id=national_id,
            checkin_date=today
        ).first()

        # 狀態檢查
        if room.status == "已預約":
            # 只允許有預約的客戶入住
            if not reservation:
                messages.error(request, '此房間已被其他客人預約')
                return redirect('dashboard')
        elif room.status == "使用中":
            messages.error(request, '此房間目前已有人入住')
            return redirect('dashboard')

        # 預約驗證
        if reservation:
            if today < reservation.checkin_date:
                messages.error(request, '還未到預約的入住日期')
                return redirect('dashboard')
            if today > reservation.checkin_date:
                messages.error(request, '已超過預約的入住日期')
                return redirect('dashboard')
            if guest_count > reservation.guest_count:
                messages.error(request, f'入住人數不能超過預約人數 {reservation.guest_count} 人')
                return redirect('dashboard')

        # 再次檢查房型可容納人數
        max_guests = {
            '單人房': 1,
            '雙人房': 2,
            '家庭房': 4,
            '豪華房': 3,
            '套房': 4
        }.get(room.room_type.name, 1)

        if guest_count > max_guests:
            messages.error(request, f'此房型最多只能容納 {max_guests} 人')
            return redirect('dashboard')

        # 建立入住記錄
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

        # 更新房間狀態
        room.status = '使用中'
        room.save()

        # 預約入住成功後，刪除此筆預約資料
        if reservation:
            reservation.delete()
            messages.success(request, '預約入住成功！')
        else:
            messages.success(request, '現場入住成功！')
        return redirect('dashboard')
    return redirect('dashboard')

@csrf_exempt
def checkout(request, room_number):
    room = get_object_or_404(Room, room_number=room_number)
    checkin = CheckIn.objects.filter(room=room).first()
    if checkin:
        customer = checkin.customer
        # 更新房間狀態
        room.status = "空房"
        room.save()
        
        # 清除行李寄放狀態（如果客戶沒有其他入住記錄）
        other_checkins = CheckIn.objects.filter(customer=customer).exclude(id=checkin.id)
        if not other_checkins.exists():
            customer.has_luggage = False
            customer.save()
        
        # 刪除 checkin 資料
        checkin.delete()
        # 如果這個客戶沒有其他 checkin，也沒有預約，則刪除客戶資料
        if not (CheckIn.objects.filter(customer=customer).exists() or 
                Reservation.objects.filter(customer=customer).exists()):
            customer.delete()
    return redirect('dashboard')

@csrf_exempt
def add_reservation(request):
    if request.method == 'POST':
        national_id = request.POST.get('national_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        room_number = request.POST.get('room_number')
        checkin_date = request.POST.get('checkin_date')
        checkout_date = request.POST.get('checkout_date')
        nights = request.POST.get('nights')
        guest_count = int(request.POST.get('guest_count', 1))

        # 檢查這個房間在指定日期是否已被預約
        room = Room.objects.get(room_number=room_number)
        conflicting_reservations = Reservation.objects.filter(
            room=room,
            checkout_date__gt=checkin_date,
            checkin_date__lt=checkout_date
        ).exists()

        if conflicting_reservations:
            messages.error(request, '該房間在選擇的日期內已被預約')
            return redirect('dashboard')

        # 檢查入住人數是否符合房型限制
        max_guests = {
            '單人房': 1,
            '雙人房': 2,
            '家庭房': 4,
            '豪華房': 3,
            '套房': 4
        }.get(room.room_type.name, 1)

        if guest_count > max_guests:
            messages.error(request, f'此房型最多只能容納 {max_guests} 人')
            return redirect('dashboard')

        # 如果都通過驗證，建立預約
        customer, created = Customer.objects.get_or_create(
            national_id=national_id,
            defaults={'name': name, 'phone': phone}
        )
        if not created:
            customer.name = name
            customer.phone = phone
            customer.save()

        Reservation.objects.create(
            customer=customer,
            room=room,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            nights=nights,
            guest_count=guest_count
        )
        # 新增：預約成功後，將房間狀態設為「已預約」
        room.status = "已預約"
        room.save()
        messages.success(request, '預約成功！')
    return redirect('dashboard')

@csrf_exempt
def add_promotion(request):
    """新增促銷"""
    if request.method == 'POST':
        code = request.POST.get('code')
        name = request.POST.get('name')
        room_type_code = request.POST.get('room_type')
        discount = request.POST.get('discount')
        
        try:
            # 檢查必要欄位
            if not all([code, name, room_type_code, discount]):
                messages.error(request, '所有欄位都必須填寫')
                return redirect('dashboard')
                
            # 驗證折扣值
            try:
                discount = float(discount)
                if not (0 < discount <= 1):
                    messages.error(request, '折扣必須在0到1之間')
                    return redirect('dashboard')
            except ValueError:
                messages.error(request, '折扣必須是有效的數字')
                return redirect('dashboard')
                
            # 檢查促銷代碼是否已存在
            if Promotion.objects.filter(code=code).exists():
                messages.error(request, '此促銷代碼已存在')
                return redirect('dashboard')
            
            # 找到對應的房型
            try:
                room_type = RoomType.objects.get(code=room_type_code)
            except RoomType.DoesNotExist:
                messages.error(request, '找不到指定的房型')
                return redirect('dashboard')
                
            # 檢查該房型是否已有促銷
            if Promotion.objects.filter(room_type=room_type).exists():
                messages.error(request, '此房型已有促銷方案')
                return redirect('dashboard')
            
            # 建立促銷
            promotion = Promotion.objects.create(
                code=code,
                name=name,
                room_type=room_type,
                discount=discount
            )
            
            # 更新所有該房型的房間，加入促銷
            updated_count = Room.objects.filter(room_type=room_type).update(promotion=promotion)
            
            messages.success(request, f'已成功建立促銷方案「{name}」，影響 {updated_count} 間房間')
            
        except Exception as e:
            messages.error(request, f'建立促銷時發生錯誤：{str(e)}')
            
    return redirect('dashboard')

@csrf_exempt
def cancel_reservation(request):
    if request.method == 'POST':
        reservation_id = request.POST.get('reservation_id')
        try:
            reservation = Reservation.objects.get(id=reservation_id)
            room = reservation.room
            customer = reservation.customer
            checkin_date = reservation.checkin_date
            checkout_date = reservation.checkout_date
            reservation.delete()
            # 檢查該房間在此時段是否還有其他預約
            has_other = Reservation.objects.filter(
                room=room,
                checkin_date__lte=checkout_date,
                checkout_date__gte=checkin_date
            ).exists()
            if not has_other:
                room.status = "空房"
                room.save()
            # 檢查此客戶是否還有其他預約或入住資料
            has_other_reservation = Reservation.objects.filter(customer=customer).exists()
            has_other_checkin = CheckIn.objects.filter(customer=customer).exists()
            if not has_other_reservation and not has_other_checkin:
                customer.delete()
            return JsonResponse({'success': True, 'msg': '預約已取消'})
        except Reservation.DoesNotExist:
            return JsonResponse({'success': False, 'msg': '找不到此預約'})
    return JsonResponse({'success': False, 'msg': '無效請求'})