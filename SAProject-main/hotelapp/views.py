from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db import transaction
from .models import Room, Customer, CheckIn, Reservation, Promotion, RoomType
from django.utils import timezone
from django.http import JsonResponse
from datetime import datetime

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
    if request.method == 'POST':
        try:
            with transaction.atomic():
                room = Room.objects.select_for_update().get(room_number=room_number)
                national_id = request.POST.get('national_id')
                name = request.POST.get('name')
                phone = request.POST.get('phone')
                guest_count = int(request.POST.get('guest_count', 1))
                has_luggage = request.POST.get('has_luggage') == 'true'

                today = timezone.now().date()
                
                # 使用 select_for_update 確保資料一致性
                reservation = Reservation.objects.select_for_update().filter(
                    room=room,
                    customer__national_id=national_id,
                    checkin_date=today
                ).first()

                # 狀態檢查
                if room.status not in ["空房", "已預約"]:
                    messages.error(request, '此房間目前無法入住')
                    return redirect('dashboard')
                
                if room.status == "已預約" and not reservation:
                    messages.error(request, '此房間已被其他人預約')
                    return redirect('dashboard')

                # 容納人數檢查
                max_guests = {
                    '單人房': 1,
                    '雙人房': 2,
                    '家庭房': 4,
                    '豪華房': 3,
                    '套房': 4
                }.get(room.room_type.name, 1)

                if guest_count > max_guests:
                    messages.error(request, f'超過房型可容納人數，此房型最多可容納 {max_guests} 人')
                    return redirect('dashboard')

                # 建立或更新客戶資料
                customer, created = Customer.objects.get_or_create(
                    national_id=national_id,
                    defaults={'name': name, 'phone': phone, 'has_luggage': has_luggage}
                )
                
                if not created:
                    customer.name = name
                    customer.phone = phone
                    customer.has_luggage = has_luggage
                    customer.save()

                # 確保沒有其他進行中的入住記錄
                active_checkin = CheckIn.objects.filter(
                    customer=customer,
                    checkout_time__isnull=True
                ).first()
                
                if active_checkin:
                    messages.error(request, '此客戶已有進行中的入住記錄')
                    return redirect('dashboard')

                # 建立入住記錄
                checkin = CheckIn.objects.create(
                    customer=customer,
                    room=room,
                    guest_count=guest_count,
                    checkin_time=timezone.now()
                )

                # 更新房間狀態
                room.status = '使用中'
                room.save()

                # 如果是從預約入住，刪除預約記錄
                if reservation:
                    reservation.delete()
                    messages.success(request, '預約入住成功！')
                else:
                    messages.success(request, '入住成功！')

        except Exception as e:
            messages.error(request, f'入住處理時發生錯誤：{str(e)}')
        
    return redirect('dashboard')

@csrf_exempt
def checkout(request, room_number):
    try:
        with transaction.atomic():
            room = Room.objects.select_for_update().get(room_number=room_number)
            
            # 查找進行中的入住記錄
            checkin = CheckIn.objects.select_for_update().filter(
                room=room,
                checkout_time__isnull=True
            ).first()
            
            if not checkin:
                messages.error(request, '找不到進行中的入住記錄')
                return redirect('dashboard')
            
            customer = checkin.customer
            
            # 更新退房時間
            checkin.checkout_time = timezone.now()
            checkin.save()
            
            # 更新房間狀態
            room.status = "空房"
            room.save()
            
            # 清除行李寄放狀態
            other_active_checkins = CheckIn.objects.filter(
                customer=customer,
                checkout_time__isnull=True
            ).exclude(id=checkin.id).exists()
            
            if not other_active_checkins:
                customer.has_luggage = False
                customer.save()
            
            # 檢查是否需要保留客戶資料
            has_other_records = (
                Reservation.objects.filter(customer=customer).exists() or 
                CheckIn.objects.filter(customer=customer).exclude(id=checkin.id).exists()
            )
            
            if not has_other_records:
                customer.delete()
                
            messages.success(request, '退房成功！')
            
    except Room.DoesNotExist:
        messages.error(request, '找不到指定的房間')
    except Exception as e:
        messages.error(request, f'退房處理時發生錯誤：{str(e)}')
        
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
    """新增促銷方案"""
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        name = request.POST.get('name', '').strip()
        room_type_code = request.POST.get('room_type', '').strip()
        discount = request.POST.get('discount', '').strip()
        start_date = request.POST.get('start_date', '')
        end_date = request.POST.get('end_date', '')
        
        try:
            with transaction.atomic():
                # 基本欄位檢查
                if not all([code, name, room_type_code, discount]):
                    messages.error(request, '所有必填欄位都必須填寫')
                    return redirect('dashboard')
                
                # 驗證促銷代碼格式
                if not code.isalnum():
                    messages.error(request, '促銷代碼只能包含字母和數字')
                    return redirect('dashboard')
                
                # 驗證折扣值
                try:
                    discount = float(discount)
                    if not (0 < discount < 1):
                        messages.error(request, '折扣必須在0到1之間')
                        return redirect('dashboard')
                except ValueError:
                    messages.error(request, '折扣必須是有效的數字')
                    return redirect('dashboard')

                # 驗證日期
                start_date_obj = None
                end_date_obj = None
                if start_date and end_date:
                    try:
                        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                        
                        today = timezone.now().date()
                        if start_date_obj < today:
                            messages.error(request, '開始日期不能是過去的日期')
                            return redirect('dashboard')
                            
                        if end_date_obj < start_date_obj:
                            messages.error(request, '結束日期不能早於開始日期')
                            return redirect('dashboard')
                    except ValueError:
                        messages.error(request, '日期格式不正確')
                        return redirect('dashboard')

                # 檢查促銷代碼是否已存在
                if Promotion.objects.filter(code=code).exists():
                    messages.error(request, '此促銷代碼已存在')
                    return redirect('dashboard')

                # 找到對應的房型並鎖定相關資料
                try:
                    room_type = RoomType.objects.select_for_update().get(code=room_type_code)
                except RoomType.DoesNotExist:
                    messages.error(request, '找不到指定的房型')
                    return redirect('dashboard')

                # 檢查該房型是否已有有效的促銷
                today = timezone.now().date()
                existing_promotion = Promotion.objects.select_for_update().filter(
                    room_type=room_type,
                    is_active=True
                ).first()

                if existing_promotion:
                    # 檢查現有促銷是否還在有效期內
                    if existing_promotion.is_valid():
                        messages.error(request, '此房型已有有效的促銷方案')
                        return redirect('dashboard')
                    else:
                        # 如果現有促銷已過期，將其停用並解除房間關聯
                        Room.objects.filter(promotion=existing_promotion).update(promotion=None)
                        existing_promotion.is_active = False
                        existing_promotion.save()

                # 建立新促銷方案
                promotion = Promotion.objects.create(
                    code=code,
                    name=name,
                    room_type=room_type,
                    discount=discount,
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    is_active=True
                )

                # 更新該房型的所有可用房間
                updated_count = Room.objects.filter(
                    room_type=room_type,
                    status__in=['空房', '已預約']  # 只更新空房和已預約的房間
                ).update(promotion=promotion)

                messages.success(request, f'已成功建立促銷方案「{name}」，影響 {updated_count} 間房間')

        except Exception as e:
            messages.error(request, f'建立促銷時發生錯誤：{str(e)}')

    return redirect('dashboard')

@csrf_exempt
def cancel_reservation(request):
    if request.method == 'POST':
        reservation_id = request.POST.get('reservation_id')
        if not reservation_id:
            return JsonResponse({'success': False, 'msg': '預約編號不能為空'})
        
        try:
            with transaction.atomic():
                reservation = Reservation.objects.select_for_update().get(id=reservation_id)
                room = reservation.room
                customer = reservation.customer
                
                # 刪除預約
                reservation.delete()
                
                # 檢查是否還有其他預約，使用 select_for_update 確保資料一致性
                has_other_reservations = Reservation.objects.filter(room=room).exists()
                if not has_other_reservations:
                    room.status = "空房"
                    room.save()
                
                # 檢查並清理無用的客戶資料
                has_other_records = (
                    Reservation.objects.filter(customer=customer).exists() or 
                    CheckIn.objects.filter(customer=customer).exists()
                )
                if not has_other_records:
                    customer.delete()
                
                return JsonResponse({'success': True, 'msg': '預約已成功取消'})
                
        except Reservation.DoesNotExist:
            return JsonResponse({'success': False, 'msg': '找不到該預約'})
        except Exception as e:
            return JsonResponse({'success': False, 'msg': f'取消預約時發生錯誤：{str(e)}'})
    
    return JsonResponse({'success': False, 'msg': '無效請求'})

@csrf_exempt
def delete_promotion(request, code):
    """刪除促銷方案"""
    if request.method == 'POST':
        try:
            promotion = get_object_or_404(Promotion, code=code)
            
            # 先將使用此促銷的房間的促銷設為 None
            Room.objects.filter(promotion=promotion).update(promotion=None)
            
            # 刪除促銷方案
            promotion.delete()
            
            messages.success(request, f'已成功刪除促銷方案「{promotion.name}」')
        except Exception as e:
            messages.error(request, f'刪除促銷時發生錯誤：{str(e)}')
    
    return redirect('dashboard')