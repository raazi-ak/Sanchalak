## schemabot/api/models/requests.py

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from conversation import MessageRole
import re

class StartConversationRequest(BaseModel):
    """Request to start a new conversation"""
    scheme_code: str = Field(..., description="Government scheme code")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    language: str = Field(default="en", description="Preferred language")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('scheme_code')
    def validate_scheme_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme code cannot be empty")
        # Validate scheme code format (alphanumeric with underscores)
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("Scheme code must contain only alphanumeric characters and underscores")
        return v.strip().upper()
    
    @validator('language')
    def validate_language(cls, v):
        supported_languages = ['en', 'hi', 'bn', 'te', 'ta', 'mr', 'gu', 'kn', 'ml', 'or', 'pa', 'as']
        if v not in supported_languages:
            raise ValueError(f"Language '{v}' not supported. Supported languages: {', '.join(supported_languages)}")
        return v

class SendMessageRequest(BaseModel):
    """Request to send a message in conversation"""
    conversation_id: str = Field(..., description="Conversation identifier")
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    role: MessageRole = Field(default=MessageRole.USER, description="Message role")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional message metadata")
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        
        # Remove potentially harmful content
        cleaned = v.strip()
        
        # Check for spam patterns
        if len(set(cleaned)) < 3:  # Too many repeated characters
            raise ValueError("Message appears to be spam")
        
        return cleaned

class GetConversationRequest(BaseModel):
    """Request to get conversation details"""
    conversation_id: str = Field(..., description="Conversation identifier")
    include_messages: bool = Field(default=True, description="Whether to include message history")
    include_metadata: bool = Field(default=False, description="Whether to include detailed metadata")

class ListConversationsRequest(BaseModel):
    """Request to list conversations with filtering"""
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    scheme_code: Optional[str] = Field(None, description="Filter by scheme code")
    status: Optional[str] = Field(None, description="Filter by conversation status")
    start_date: Optional[datetime] = Field(None, description="Filter conversations started after this date")
    end_date: Optional[datetime] = Field(None, description="Filter conversations started before this date")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=20, ge=1, le=100, description="Number of items per page")
    
    # Sorting
    sort_by: str = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", description="Sort order")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        allowed_fields = ['created_at', 'updated_at', 'status', 'scheme_code']
        if v not in allowed_fields:
            raise ValueError(f"Invalid sort field. Allowed: {', '.join(allowed_fields)}")
        return v
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError("Sort order must be 'asc' or 'desc'")
        return v

class DirectEligibilityCheckRequest(BaseModel):
    """Request for direct eligibility check without conversation"""
    scheme_code: str = Field(..., description="Government scheme code")
    farmer_data: Dict[str, Any] = Field(..., description="Farmer's data for eligibility check")
    include_recommendations: bool = Field(default=True, description="Include recommendations in response")
    include_detailed_results: bool = Field(default=False, description="Include detailed rule evaluation results")
    
    @validator('scheme_code')
    def validate_scheme_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme code cannot be empty")
        return v.strip().upper()
    
    @validator('farmer_data')
    def validate_farmer_data(cls, v):
        if not v:
            raise ValueError("Farmer data cannot be empty")
        
        # Basic validation for common fields
        if 'age' in v:
            age = v['age']
            if not isinstance(age, (int, float)) or age < 0 or age > 120:
                raise ValueError("Age must be a number between 0 and 120")
        
        if 'annual_income' in v:
            income = v['annual_income']
            if not isinstance(income, (int, float)) or income < 0:
                raise ValueError("Annual income must be a non-negative number")
        
        return v

class UpdateConversationRequest(BaseModel):
    """Request to update conversation settings"""
    conversation_id: str = Field(..., description="Conversation identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata to update")
    timeout_minutes: Optional[int] = Field(None, ge=5, le=120, description="Conversation timeout in minutes")
    max_attempts_per_field: Optional[int] = Field(None, ge=1, le=10, description="Maximum attempts per field")

class EndConversationRequest(BaseModel):
    """Request to end a conversation"""
    conversation_id: str = Field(..., description="Conversation identifier")
    reason: Optional[str] = Field(None, description="Reason for ending conversation")
    save_history: bool = Field(default=True, description="Whether to save conversation history")

class GetSchemeInfoRequest(BaseModel):
    """Request to get scheme information"""
    scheme_code: str = Field(..., description="Government scheme code")
    include_rules: bool = Field(default=False, description="Include eligibility rules")
    include_benefits: bool = Field(default=True, description="Include benefits information")
    include_documents: bool = Field(default=True, description="Include required documents")
    language: str = Field(default="en", description="Language for response")
    
    @validator('scheme_code')
    def validate_scheme_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme code cannot be empty")
        return v.strip().upper()

class ListSchemesRequest(BaseModel):
    """Request to list available schemes"""
    category: Optional[str] = Field(None, description="Filter by scheme category")
    ministry: Optional[str] = Field(None, description="Filter by ministry")
    status: str = Field(default="active", description="Filter by scheme status")
    search: Optional[str] = Field(None, description="Search in scheme name/description")
    
    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=50, ge=1, le=100, description="Number of items per page")

class ConversationMetricsRequest(BaseModel):
    """Request for conversation metrics and analytics"""
    start_date: Optional[datetime] = Field(None, description="Start date for metrics")
    end_date: Optional[datetime] = Field(None, description="End date for metrics")
    scheme_code: Optional[str] = Field(None, description="Filter by specific scheme")
    user_id: Optional[str] = Field(None, description="Filter by specific user")
    
    # Metric types
    include_completion_rates: bool = Field(default=True, description="Include completion rate metrics")
    include_eligibility_stats: bool = Field(default=True, description="Include eligibility statistics")
    include_performance_metrics: bool = Field(default=False, description="Include performance metrics")
    include_user_behavior: bool = Field(default=False, description="Include user behavior analytics")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and values['start_date'] and v:
            if v < values['start_date']:
                raise ValueError("End date must be after start date")
        return v

class ValidateSchemeRequest(BaseModel):
    """Request to validate a scheme definition"""
    scheme_yaml: str = Field(..., description="YAML content of the scheme")
    strict_validation: bool = Field(default=True, description="Enable strict validation")
    
    @validator('scheme_yaml')
    def validate_yaml_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme YAML content cannot be empty")
        return v.strip()

class BulkEligibilityCheckRequest(BaseModel):
    """Request for bulk eligibility checks"""
    scheme_code: str = Field(..., description="Government scheme code")
    farmer_data_list: List[Dict[str, Any]] = Field(..., min_items=1, max_items=100, description="List of farmer data")
    include_detailed_results: bool = Field(default=False, description="Include detailed results for each check")
    
    @validator('scheme_code')
    def validate_scheme_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme code cannot be empty")
        return v.strip().upper()
    
    @validator('farmer_data_list')
    def validate_farmer_data_list(cls, v):
        if not v:
            raise ValueError("Farmer data list cannot be empty")
        
        # Ensure each entry has some basic structure
        for i, data in enumerate(v):
            if not isinstance(data, dict):
                raise ValueError(f"Farmer data at index {i} must be a dictionary")
            if not data:
                raise ValueError(f"Farmer data at index {i} is empty")
        
        return v

class ExportConversationRequest(BaseModel):
    """Request to export conversation data"""
    conversation_ids: List[str] = Field(..., min_items=1, max_items=50, description="List of conversation IDs to export")
    export_format: str = Field(default="json", description="Export format")
    include_messages: bool = Field(default=True, description="Include message history")
    include_metadata: bool = Field(default=True, description="Include metadata")
    anonymize_data: bool = Field(default=True, description="Anonymize sensitive data")
    
    @validator('export_format')
    def validate_export_format(cls, v):
        allowed_formats = ['json', 'csv', 'xlsx']
        if v not in allowed_formats:
            raise ValueError(f"Export format must be one of: {', '.join(allowed_formats)}")
        return v

class HealthCheckRequest(BaseModel):
    """Request for system health check"""
    check_dependencies: bool = Field(default=True, description="Check external dependencies")
    include_metrics: bool = Field(default=False, description="Include performance metrics")
    detailed: bool = Field(default=False, description="Return detailed health information")

class CreateSchemeRequest(BaseModel):
    """Request to create a new scheme (admin only)"""
    scheme_yaml: str = Field(..., description="YAML content of the scheme")
    validate_only: bool = Field(default=False, description="Only validate, don't create")
    force_update: bool = Field(default=False, description="Force update if scheme exists")
    
    @validator('scheme_yaml')
    def validate_yaml_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme YAML content cannot be empty")
        return v.strip()

class UpdateSchemeRequest(BaseModel):
    """Request to update an existing scheme (admin only)"""
    scheme_code: str = Field(..., description="Scheme code to update")
    scheme_yaml: str = Field(..., description="Updated YAML content")
    version_comment: Optional[str] = Field(None, description="Comment for this version")
    
    @validator('scheme_code')
    def validate_scheme_code(cls, v):
        if not v or not v.strip():
            raise ValueError("Scheme code cannot be empty")
        return v.strip().upper()

class DeleteSchemeRequest(BaseModel):
    """Request to delete a scheme (admin only)"""
    scheme_code: str = Field(..., description="Scheme code to delete")
    confirmation: str = Field(..., description="Confirmation string")
    backup_data: bool = Field(default=True, description="Create backup before deletion")
    
    @validator('confirmation')
    def validate_confirmation(cls, v, values):
        if 'scheme_code' in values and v != f"DELETE_{values['scheme_code']}":
            raise ValueError(f"Confirmation must be 'DELETE_{values['scheme_code']}'")
        return v