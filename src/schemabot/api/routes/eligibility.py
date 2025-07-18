"""
Eligibility Check Endpoints
Provide direct eligibility evaluation endpoints without conversational flow.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from datetime import datetime, timezone

from src.schemabot.api.models.requests import EligibilityCheckRequest, BulkEligibilityRequest
from src.schemabot.api.models.responses import EligibilityResponse, BulkEligibilityResponse
from src.schemabot.core.eligibility.checker import EligibilityChecker
from src.schemabot.core.utils.logger import get_logger
from src.schemabot.core.utils.monitoring import get_metrics_collector

logger = get_logger(__name__)
router = APIRouter(prefix="/eligibility", tags=["eligibility"])

eligibility_checker = EligibilityChecker()


@router.post("/check", response_model=EligibilityResponse)
async def check_eligibility(
    request: EligibilityCheckRequest,
    metrics_collector = Depends(get_metrics_collector)
):
    """
    Check eligibility for a single applicant based on provided data.
    """
    try:
        result = await eligibility_checker.check_eligibility(
            request.scheme_code,
            request.applicant_data
        )

        await metrics_collector.record_api_call("check_eligibility", 1)

        return EligibilityResponse(
            scheme_code=request.scheme_code,
            is_eligible=result.is_eligible,
            failure_reasons=result.failure_reasons,
            score=result.score,
            evaluated_at=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Eligibility check failed for scheme {request.scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Eligibility check failed"
        )


@router.post("/bulk", response_model=BulkEligibilityResponse)
async def bulk_eligibility(
    request: BulkEligibilityRequest,
    metrics_collector = Depends(get_metrics_collector)
):
    """
    Perform eligibility checks in bulk.
    """
    try:
        results = []
        for applicant in request.applicants:
            result = await eligibility_checker.check_eligibility(
                request.scheme_code,
                applicant
            )
            results.append({
                "applicant_id": applicant.get("id"),
                "is_eligible": result.is_eligible,
                "failure_reasons": result.failure_reasons,
                "score": result.score
            })

        await metrics_collector.record_api_call("bulk_eligibility", len(results))

        return BulkEligibilityResponse(
            scheme_code=request.scheme_code,
            results=results,
            processed_at=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Bulk eligibility check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk eligibility check failed"
        )