from django.contrib import admin
from .models import FarmerUser, ChatSession, SessionMessage, SchemeEligibility

@admin.register(FarmerUser)
class FarmerUserAdmin(admin.ModelAdmin):
    list_display = ['farmer_id', 'telegram_user_id', 'name', 'phone', 'verification_status', 'language_preference', 'created_at']
    list_filter = ['verification_status', 'ekyc_status', 'language_preference', 'created_at']
    search_fields = ['farmer_id', 'name', 'phone', 'telegram_user_id']
    readonly_fields = ['farmer_id', 'created_at']

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'farmer_id', 'telegram_user_id', 'status', 'start_time', 'total_messages']
    list_filter = ['status', 'start_time']
    search_fields = ['session_id', 'farmer_id', 'telegram_user_id']
    readonly_fields = ['session_id', 'start_time']

@admin.register(SessionMessage)
class SessionMessageAdmin(admin.ModelAdmin):
    list_display = ['message_id', 'session_id', 'message_type', 'timestamp', 'processed']
    list_filter = ['message_type', 'processed', 'timestamp']
    search_fields = ['message_id', 'session_id', 'content']
    readonly_fields = ['message_id', 'timestamp']

@admin.register(SchemeEligibility)
class SchemeEligibilityAdmin(admin.ModelAdmin):
    list_display = ['check_id', 'farmer_id', 'scheme_name', 'eligibility_status', 'form_generated', 'created_at']
    list_filter = ['eligibility_status', 'form_generated', 'created_at']
    search_fields = ['check_id', 'farmer_id', 'scheme_name', 'scheme_code']
    readonly_fields = ['check_id', 'created_at'] 