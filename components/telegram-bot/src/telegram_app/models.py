from djongo import models
from django.utils import timezone
import uuid


class FarmerUser(models.Model):
    """User model for farmer information - stored in sanchalak_users DB"""
    
    farmer_id = models.CharField(max_length=100, unique=True, primary_key=True, default=uuid.uuid4)
    telegram_user_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    language_preference = models.CharField(max_length=10, default='hindi')
    
    # Verification status
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    
    # eKYC information
    ekyc_status = models.CharField(
        max_length=20,
        choices=[
            ('not_started', 'Not Started'),
            ('aadhaar_verified', 'Aadhaar Verified'),
            ('photo_verified', 'Photo Verified'),
            ('skipped', 'Skipped')
        ],
        default='not_started'
    )
    aadhaar_last_digits = models.CharField(max_length=4, null=True, blank=True)
    photo_verification_status = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    ekyc_completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'farmer_users'
    
    def __str__(self):
        return f"{self.name or 'User'} ({self.telegram_user_id})"


class ChatSession(models.Model):
    """Session model for chat sessions - stored in sanchalak_sessions DB"""
    
    session_id = models.CharField(max_length=100, unique=True, primary_key=True, default=uuid.uuid4)
    farmer_id = models.CharField(max_length=100)
    telegram_user_id = models.BigIntegerField()
    
    # Session status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('expired', 'Expired')
        ],
        default='active'
    )
    
    # Session data
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    total_messages = models.IntegerField(default=0)
    
    # Processing results
    processing_result = models.JSONField(null=True, blank=True)
    schemes_identified = models.JSONField(default=list)
    forms_generated = models.JSONField(default=list)
    
    class Meta:
        db_table = 'chat_sessions'
    
    def __str__(self):
        return f"Session {self.session_id} - {self.status}"


class SessionMessage(models.Model):
    """Individual messages within a session"""
    
    message_id = models.CharField(max_length=100, unique=True, primary_key=True, default=uuid.uuid4)
    session_id = models.CharField(max_length=100)
    
    # Message details
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('text', 'Text'),
            ('voice', 'Voice'),
            ('photo', 'Photo'),
            ('contact', 'Contact'),
            ('system', 'System')
        ]
    )
    content = models.TextField()
    file_path = models.CharField(max_length=500, null=True, blank=True)
    
    # Metadata
    timestamp = models.DateTimeField(default=timezone.now)
    processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'session_messages'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Message {self.message_id} - {self.message_type}"


class SchemeEligibility(models.Model):
    """Track scheme eligibility checks"""
    
    check_id = models.CharField(max_length=100, unique=True, primary_key=True, default=uuid.uuid4)
    farmer_id = models.CharField(max_length=100)
    session_id = models.CharField(max_length=100)
    
    # Scheme details
    scheme_name = models.CharField(max_length=200)
    scheme_code = models.CharField(max_length=50)
    eligibility_status = models.CharField(
        max_length=20,
        choices=[
            ('eligible', 'Eligible'),
            ('not_eligible', 'Not Eligible'),
            ('pending', 'Pending Review')
        ]
    )
    eligibility_reason = models.TextField(null=True, blank=True)
    
    # Form generation
    form_generated = models.BooleanField(default=False)
    form_path = models.CharField(max_length=500, null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'scheme_eligibility'
    
    def __str__(self):
        return f"{self.scheme_name} - {self.eligibility_status}" 