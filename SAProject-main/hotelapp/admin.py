from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
import csv
from datetime import datetime
from django.contrib.admin import SimpleListFilter
from .models import Customer, RoomType, Promotion, Room, Reservation, CheckIn

# 自定義管理站點標題
admin.site.site_header = '飯店管理系統'
admin.site.site_title = '飯店管理系統'
admin.site.index_title = '管理介面'

# CSV匯出功能的基類
class ExportCsvMixin:
    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename={meta.verbose_name_plural}.csv'
        response.write('\ufeff'.encode('utf8'))

        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response
    export_as_csv.short_description = '匯出所選項目為 CSV'

# 客戶管理
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('name', 'national_id', 'phone', 'luggage_status', 'reservation_count', 'checkin_count')
    search_fields = ('name', 'national_id', 'phone')
    list_filter = ('has_luggage',)
    ordering = ('name',)
    actions = ['export_as_csv']
    
    def luggage_status(self, obj):
        if obj.has_luggage:
            return format_html('<span style="color: green; font-weight: bold;">✓ 有行李</span>')
        return format_html('<span style="color: red;">✗ 無行李</span>')
    
    def reservation_count(self, obj):
        count = Reservation.objects.filter(customer=obj).count()
        return format_html('<span style="color: #3498db;">{}</span>', count)
        
    def checkin_count(self, obj):
        count = CheckIn.objects.filter(customer=obj).count()
        return format_html('<span style="color: #2ecc71;">{}</span>', count)
    
    luggage_status.short_description = '行李狀態'
    reservation_count.short_description = '預約次數'
    checkin_count.short_description = '入住次數'
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('name', 'national_id', 'phone')
        }),
        ('其他資訊', {
            'fields': ('has_luggage',),
            'classes': ('collapse',)
        }),
    )

# 房型管理
@admin.register(RoomType)
class RoomTypeAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('name', 'code', 'room_count', 'available_room_count')
    search_fields = ('name', 'code')
    ordering = ('code',)
    actions = ['export_as_csv']
    
    def room_count(self, obj):
        count = Room.objects.filter(room_type=obj).count()
        return format_html('<span style="color: #3498db;">{} 間</span>', count)
        
    def available_room_count(self, obj):
        count = Room.objects.filter(room_type=obj, status='空房').count()
        return format_html('<span style="color: #2ecc71;">{} 間</span>', count)
    
    room_count.short_description = '總房間數'
    available_room_count.short_description = '可用房間數'

# 促銷管理
class PromotionStatusFilter(SimpleListFilter):
    title = '促銷狀態'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('active', '使用中'),
            ('inactive', '未使用'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(rooms__isnull=False).distinct()
        if self.value() == 'inactive':
            return queryset.filter(rooms__isnull=True)

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('name', 'code', 'room_type', 'discount_display', 'affected_rooms', 'promotion_status')
    search_fields = ('name', 'code')
    list_filter = (PromotionStatusFilter, 'room_type')
    ordering = ('-discount',)
    actions = ['export_as_csv']
    
    def discount_display(self, obj):
        return format_html('<span style="color: #e67e22; font-weight: bold;">{}</span>折', 
                         int(obj.discount * 100))
    
    def affected_rooms(self, obj):
        count = Room.objects.filter(promotion=obj).count()
        return format_html('<span style="color: #3498db;">{} 間</span>', count)
        
    def promotion_status(self, obj):
        count = Room.objects.filter(promotion=obj).count()
        if count > 0:
            return format_html('<span style="background-color: #2ecc71; color: white; padding: 3px 8px; border-radius: 3px;">使用中</span>')
        return format_html('<span style="background-color: #95a5a6; color: white; padding: 3px 8px; border-radius: 3px;">未使用</span>')
    
    discount_display.short_description = '折扣'
    affected_rooms.short_description = '影響房間數'
    promotion_status.short_description = '狀態'
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('name', 'code', 'room_type')
        }),
        ('折扣設定', {
            'fields': ('discount',),
            'description': '請輸入0到1之間的小數，例如0.8表示8折'
        }),
    )

# 房間管理
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('room_number', 'room_type', 'price_display', 'status_tag', 'current_promotion', 'current_guest')
    list_filter = ('room_type', 'status', 'promotion')
    search_fields = ('room_number',)
    ordering = ('room_number',)
    actions = ['export_as_csv']
    
    def price_display(self, obj):
        if obj.promotion:
            original_price = obj.price
            discounted_price = obj.price * obj.promotion.discount
            return format_html(
                '<span style="text-decoration: line-through; color: #95a5a6;">NT${}</span> '
                '<span style="color: #e74c3c; font-weight: bold;">NT${}</span>',
                int(original_price),
                int(discounted_price)
            )
        return format_html('<span style="color: #2c3e50;">NT${}</span>', int(obj.price))
    
    def status_tag(self, obj):
        colors = {
            '空房': '#2ecc71',
            '使用中': '#e74c3c',
            '已預約': '#f1c40f',
            '清潔中': '#3498db'
        }
        color = colors.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px;">{}</span>',
            color, obj.status
        )
    
    def current_promotion(self, obj):
        if obj.promotion:
            return format_html(
                '<span style="color: #e67e22; font-weight: bold;">{} ({}折)</span>',
                obj.promotion.name,
                int(obj.promotion.discount * 100)
            )
        return format_html('<span style="color: #95a5a6;">無促銷</span>')
        
    def current_guest(self, obj):
        current_checkin = CheckIn.objects.filter(
            room=obj,
            checkout_time__isnull=True
        ).first()
        if current_checkin:
            return format_html(
                '<span style="color: #2980b9;">{}</span>',
                current_checkin.customer.name
            )
        return format_html('<span style="color: #95a5a6;">-</span>')
    
    price_display.short_description = '房價'
    status_tag.short_description = '狀態'
    current_promotion.short_description = '當前促銷'
    current_guest.short_description = '當前住客'
    
    fieldsets = (
        ('基本資訊', {
            'fields': ('room_number', 'room_type', 'price')
        }),
        ('狀態資訊', {
            'fields': ('status', 'promotion'),
        }),
    )

# 預約管理
@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('customer_info', 'room_info', 'date_range', 'nights', 'reservation_status')
    list_filter = ('checkin_date', 'checkout_date', 'room__room_type')
    search_fields = ('customer__name', 'customer__phone', 'room__room_number')
    date_hierarchy = 'checkin_date'
    ordering = ('-checkin_date',)
    actions = ['export_as_csv']
    
    def customer_info(self, obj):
        return format_html(
            '{}<br><span style="color: #7f8c8d; font-size: 0.8em;">📱 {}</span>',
            obj.customer.name,
            obj.customer.phone
        )
    
    def room_info(self, obj):
        return format_html(
            '{}號房<br><span style="color: #7f8c8d; font-size: 0.8em;">{}</span>',
            obj.room.room_number,
            obj.room.room_type.name
        )
        
    def date_range(self, obj):
        return format_html(
            '{}  <span style="color: #95a5a6;">→</span>  {}',
            obj.checkin_date.strftime('%Y/%m/%d'),
            obj.checkout_date.strftime('%Y/%m/%d')
        )
        
    def reservation_status(self, obj):
        today = datetime.now().date()
        if obj.checkout_date < today:
            return format_html(
                '<span style="background-color: #95a5a6; color: white; '
                'padding: 3px 8px; border-radius: 3px;">已結束</span>'
            )
        elif obj.checkin_date <= today <= obj.checkout_date:
            return format_html(
                '<span style="background-color: #2ecc71; color: white; '
                'padding: 3px 8px; border-radius: 3px;">進行中</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #3498db; color: white; '
                'padding: 3px 8px; border-radius: 3px;">即將到來</span>'
            )
    
    customer_info.short_description = '客戶資訊'
    room_info.short_description = '房間資訊'
    date_range.short_description = '住宿期間'
    reservation_status.short_description = '預約狀態'
    
    fieldsets = (
        ('客戶與房間', {
            'fields': ('customer', 'room')
        }),
        ('住宿資訊', {
            'fields': ('checkin_date', 'checkout_date', 'nights')
        }),
    )

# 入住管理
@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('customer_info', 'room_info', 'time_info', 'guest_count', 'stay_status')
    list_filter = ('checkin_time', 'checkout_time', 'room__room_type')
    search_fields = ('customer__name', 'customer__phone', 'room__room_number')
    date_hierarchy = 'checkin_time'
    ordering = ('-checkin_time',)
    actions = ['export_as_csv']
    
    def customer_info(self, obj):
        luggage_status = '🧳' if obj.customer.has_luggage else ''
        return format_html(
            '{} {}<br><span style="color: #7f8c8d; font-size: 0.8em;">📱 {}</span>',
            obj.customer.name,
            luggage_status,
            obj.customer.phone
        )
    
    def room_info(self, obj):
        return format_html(
            '{}號房<br><span style="color: #7f8c8d; font-size: 0.8em;">{}</span>',
            obj.room.room_number,
            obj.room.room_type.name
        )
        
    def time_info(self, obj):
        checkin = obj.checkin_time.strftime('%Y/%m/%d %H:%M')
        if obj.checkout_time:
            checkout = obj.checkout_time.strftime('%Y/%m/%d %H:%M')
            return format_html(
                '{}  <span style="color: #95a5a6;">→</span>  {}',
                checkin, checkout
            )
        return format_html(
            '{}<br><span style="color: #e67e22;">尚未退房</span>',
            checkin
        )
        
    def stay_status(self, obj):
        if not obj.checkout_time:
            return format_html(
                '<span style="background-color: #2ecc71; color: white; '
                'padding: 3px 8px; border-radius: 3px;">住宿中</span>'
            )
        return format_html(
            '<span style="background-color: #95a5a6; color: white; '
            'padding: 3px 8px; border-radius: 3px;">已退房</span>'
        )
    
    customer_info.short_description = '客戶資訊'
    room_info.short_description = '房間資訊'
    time_info.short_description = '時間資訊'
    stay_status.short_description = '住宿狀態'
    
    fieldsets = (
        ('住宿資訊', {
            'fields': ('customer', 'room', 'guest_count')
        }),
        ('時間資訊', {
            'fields': ('checkin_time', 'checkout_time')
        }),
    )
