#schemabot/api/models/responses.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from api.models.conversation import (
    ConversationContext, 
    ConversationStatus, 
    ConversationStage,
    Message,
    EligibilityCheckResult,
    ConversationMetrics,
    ConversationHealthCheck
)

class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = Field(default=True, description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = Field(default=False)
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    suggestion: Optional[str] = Field(None, description="Suggested action for the user")

class StartConversationResponse(BaseResponse):
    """Response for starting a new conversation"""
    conversation_id: str = Field(..., description="Unique conversation identifier")
    initial_message: str = Field(..., description="Initial bot message to display")
    scheme_name: str = Field(..., description="Human-readable scheme name")
    required_fields: List[str] = Field(..., description="Fields that need to be collected")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in minutes")
    
    class ConversationInfo(BaseModel):
        scheme_code: str
        scheme_name: str
        scheme_description: str
        benefits_summary: str
        total_fields_required: int
        
    conversation_info: ConversationInfo

class SendMessageResponse(BaseResponse):
    """Response for sending a message"""
    conversation_id: str = Field(..., description="Conversation identifier")
    bot_response: str = Field(..., description="Bot's response message")
    conversation_stage: ConversationStage = Field(..., description="Current conversation stage")
    
    # Progress information
    progress_info: Optional[Dict[str, Any]] = Field(None, description="Progress information")
    
    # Next steps
    next_field_needed: Optional[str] = Field(None, description="Next field that needs to be collected")
    field_description: Optional[str] = Field(None, description="Description of the next field")
    input_suggestions: Optional[List[str]] = Field(None, description="Suggested input formats")
    
    # Conversation control
    conversation_status: ConversationStatus = Field(..., description="Current conversation status")
    can_continue: bool = Field(default=True, description="Whether conversation can continue")
    
    # Eligibility result (if available)
    eligibility_result: Optional[EligibilityCheckResult] = Field(None, description="Eligibility check result")

class GetConversationResponse(BaseResponse):
    """Response for getting conversation details"""
    conversation: ConversationContext = Field(..., description="Complete conversation context")
    
    class ConversationSummary(BaseModel):
        conversation_id: str
        status: ConversationStatus
        stage: ConversationStage
        progress_percentage: float
        messages_count: int
        duration_minutes: float
        is_eligible: Optional[bool] = None
        eligibility_score: Optional[float] = None
        
    summary: ConversationSummary

class ListConversationsResponse(BaseResponse):
    """Response for listing conversations"""
    conversations: List[ConversationContext] = Field(..., description="List of conversations")
    
    class PaginationInfo(BaseModel):
        current_page: int
        page_size: int
        total_pages: int
        total_items: int
        has_next: bool
        has_previous: bool
        
    pagination: PaginationInfo
    
    class FilterInfo(BaseModel):
        applied_filters: Dict[str, Any]
        available_filters: Dict[str, List[str]]
        
    filter_info: Optional[FilterInfo] = None

class DirectEligibilityCheckResponse(BaseResponse):
    """Response for direct eligibility check"""
    eligibility_result: EligibilityCheckResult = Field(..., description="Detailed eligibility result")
    
    class ProcessingInfo(BaseModel):
        processing_time_ms: float
        rules_evaluated: int
        data_quality_score: float
        
    processing_info: ProcessingInfo
    
    # Detailed breakdown
    rule_breakdown: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed rule evaluation results")
    improvement_path: Optional[List[str]] = Field(None, description="Steps to improve eligibility")
    
    # Alternative schemes
    alternative_schemes: Optional[List[str]] = Field(None, description="Other schemes the user might be eligible for")

class SchemeInfoResponse(BaseResponse):
    """Response for scheme information"""
    
    class SchemeDetails(BaseModel):
        code: str
        name: str
        ministry: str
        description: str
        launched_on: str
        status: str
        category: str
        
    scheme_details: SchemeDetails
    
    class BenefitInfo(BaseModel):
        type: str
        description: str
        amount: Optional[float] = None
        frequency: Optional[str] = None
        
    benefits: List[BenefitInfo]
    
    required_documents: List[str]
    application_modes: List[str]
    
    # Eligibility summary
    eligibility_summary: Optional[str] = Field(None, description="Human-readable eligibility summary")
    key_requirements: Optional[List[str]] = Field(None, description="Key eligibility requirements")
    
    # Additional info
    target_audience: Optional[str] = Field(None, description="Target audience description")
    success_rate: Optional[float] = Field(None, description="Historical success rate")

class ListSchemesResponse(BaseResponse):
    """Response for listing schemes"""
    
    class SchemeListItem(BaseModel):
        code: str
        name: str
        ministry: str
        category: str
        status: str
        description: str
        benefits_count: int
        popularity_score: Optional[float] = None
        
    schemes: List[SchemeListItem]
    
    class CategoryInfo(BaseModel):
        category_name: str
        scheme_count: int
        
    categories: List[CategoryInfo]
    
    class MinistryInfo(BaseModel):
        ministry_name: str
        scheme_count: int
        
    ministries: List[MinistryInfo]
    
    total_schemes: int

class ConversationMetricsResponse(BaseResponse):
    """Response for conversation metrics"""
    metrics: ConversationMetrics = Field(..., description="Comprehensive conversation metrics")
    
    class TrendData(BaseModel):
        period: str
        value: float
        change_percentage: Optional[float] = None
        
    trends: Optional[Dict[str, List[TrendData]]] = Field(None, description="Trend data over time")
    
    class InsightData(BaseModel):
        insight_type: str
        title: str
        description: str
        impact_level: str
        recommendation: Optional[str] = None
        
    insights: List[InsightData] = Field(default_factory=list, description="Actionable insights")

class ValidationResponse(BaseResponse):
    """Response for scheme validation"""
    is_valid: bool = Field(..., description="Whether the scheme is valid")
    
    class ValidationError(BaseModel):
        error_type: str
        field_path: str
        message: str
        severity: str
        
    validation_errors: List[ValidationError] = Field(default_factory=list)
    
    class ValidationWarning(BaseModel):
        warning_type: str
        field_path: str
        message: str
        suggestion: Optional[str] = None
        
    validation_warnings: List[ValidationWarning] = Field(default_factory=list)
    
    # Scheme info if valid
    scheme_info: Optional[Dict[str, Any]] = Field(None, description="Parsed scheme information")

class BulkEligibilityCheckResponse(BaseResponse):
    """Response for bulk eligibility checks"""
    
    class BulkResult(BaseModel):
        index: int
        farmer_id: Optional[str] = None
        eligibility_result: EligibilityCheckResult
        processing_time_ms: float
        
    results: List[BulkResult] = Field(..., description="Individual eligibility results")
    
    class BulkSummary(BaseModel):
        total_checked: int
        eligible_count: int
        ineligible_count: int
        error_count: int
        average_score: float
        processing_time_total_ms: float
        
    summary: BulkSummary

class ExportConversationResponse(BaseResponse):
    """Response for conversation export"""
    export_id: str = Field(..., description="Unique export identifier")
    download_url: str = Field(..., description="URL to download the export")
    export_format: str = Field(..., description="Format of the exported data")
    file_size_bytes: int = Field(..., description="Size of the exported file")
    expires_at: datetime = Field(..., description="When the download link expires")
    
    class ExportSummary(BaseModel):
        conversations_exported: int
        total_messages: int
        date_range: str
        anonymized: bool
        
    export_summary: ExportSummary

class HealthCheckResponse(BaseResponse):
    """Response for health check"""
    health_status: ConversationHealthCheck = Field(..., description="Detailed health status")
    
    class ServiceInfo(BaseModel):
        service_name: str
        version: str
        uptime_seconds: float
        environment: str
        
    service_info: ServiceInfo
    
    class DependencyStatus(BaseModel):
        service_name: str
        status: str
        response_time_ms: Optional[float] = None
        last_checked: datetime
        error_message: Optional[str] = None
        
    dependencies: List[DependencyStatus] = Field(default_factory=list)

class OperationResponse(BaseResponse):
    """Generic response for operations (create, update, delete)"""
    operation: str = Field(..., description="Operation performed")
    resource_id: Optional[str] = Field(None, description="ID of the affected resource")
    affected_count: int = Field(default=1, description="Number of resources affected")
    
    class OperationDetails(BaseModel):
        operation_time_ms: float
        validation_passed: bool
        backup_created: Optional[bool] = None
        rollback_available: Optional[bool] = None
        
    operation_details: Optional[OperationDetails] = None

class StatisticsResponse(BaseResponse):
    """Response for various statistics"""
    
    class StatisticItem(BaseModel):
        metric_name: str
        value: Union[int, float, str]
        unit: Optional[str] = None
        change_percentage: Optional[float] = None
        trend: Optional[str] = None  # "up", "down", "stable"
        
    statistics: List[StatisticItem] = Field(..., description="List of statistics")
    
    class ChartData(BaseModel):
        chart_type: str
        title: str
        data: List[Dict[str, Any]]
        
    charts: Optional[List[ChartData]] = Field(None, description="Chart data for visualization")
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data_period: Optional[str] = Field(None, description="Time period for the statistics")

class PredictionResponse(BaseResponse):
    """Response for prediction/recommendation endpoints"""
    
    class Prediction(BaseModel):
        prediction_type: str
        value: Union[int, float, str, bool]
        confidence: float = Field(ge=0, le=1, description="Confidence score 0-1")
        reasoning: Optional[str] = None
        
    predictions: List[Prediction] = Field(..., description="List of predictions")
    
    class Recommendation(BaseModel):
        recommendation_type: str
        title: str
        description: str
        priority: str  # "high", "medium", "low"
        estimated_impact: Optional[str] = None
        
    recommendations: List[Recommendation] = Field(default_factory=list)
    
    model_version: Optional[str] = Field(None, description="Version of the prediction model used")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class ConfigurationResponse(BaseResponse):
    """Response for configuration endpoints"""
    
    class ConfigItem(BaseModel):
        key: str
        value: Any
        description: Optional[str] = None
        is_sensitive: bool = False
        last_updated: datetime
        
    configuration: List[ConfigItem] = Field(..., description="List of configuration items")
    
    environment: str = Field(..., description="Current environment")
    version: str = Field(..., description="Application version")
    
    class FeatureFlag(BaseModel):
        feature_name: str
        enabled: bool
        description: Optional[str] = None
        
    feature_flags: Optional[List[FeatureFlag]] = Field(None, description="Active feature flags")

# Response type unions for different endpoints
ConversationResponse = Union[
    StartConversationResponse,
    SendMessageResponse,
    GetConversationResponse,
    ListConversationsResponse
]

EligibilityResponse = Union[
    DirectEligibilityCheckResponse,
    BulkEligibilityCheckResponse
]

SchemeResponse = Union[
    SchemeInfoResponse,
    ListSchemesResponse,
    ValidationResponse
]

AdminResponse = Union[
    OperationResponse,
    ExportConversationResponse,
    StatisticsResponse,
    ConfigurationResponse
]