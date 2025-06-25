"""
Government schemes router for the Farmer AI Pipeline
Handles scheme search, eligibility checking, and management
"""

import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from models import (
    FarmerInfo,
    GovernmentScheme,
    EligibilityResponse,
    EligibilityCheck,
    VectorSearchRequest,
    VectorSearchResult
)
from utils.error_handeller import (
    raise_eligibility_error,
    raise_vector_db_error,
    EligibilityCheckError,
    VectorDatabaseError
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Create router instance
router = APIRouter(
    prefix="/schemes",
    tags=["schemes"],
    responses={
        400: {"description": "Invalid request data"},
        404: {"description": "Scheme not found"},
        500: {"description": "Internal server error"}
    }
)

# Dependencies

async def get_eligibility_agent():
    """Dependency to get the eligibility checking agent"""
    from main import agents
    if "eligibility" not in agents:
        raise HTTPException(status_code=503, detail="Eligibility service unavailable")
    return agents["eligibility"]

async def get_vector_db_agent():
    """Dependency to get the vector database agent"""
    from main import agents
    if "vector_db" not in agents:
        raise HTTPException(status_code=503, detail="Vector database service unavailable")
    return agents["vector_db"]

async def get_scraper_agent():
    """Dependency to get the web scraper agent"""
    from main import agents
    if "scraper" not in agents:
        raise HTTPException(status_code=503, detail="Web scraper service unavailable")
    return agents["scraper"]

# Endpoints

@router.post("/check-eligibility", response_model=EligibilityResponse)
async def check_eligibility(
    farmer_info: FarmerInfo,
    explain_decisions: bool = True,
    eligibility_agent = Depends(get_eligibility_agent)
):
    """
    Check farmer eligibility for government schemes
    
    - **farmer_info**: Complete farmer information
    - **explain_decisions**: Include detailed explanations for decisions
    
    Returns eligibility status for all relevant schemes
    """
    logger.info("Checking farmer eligibility for schemes")
    
    try:
        # Validate farmer info
        if not farmer_info.state:
            raise_eligibility_error(
                "State information is required for eligibility checking",
                {"missing_fields": ["state"]}
            )
        
        # Check eligibility
        result = await eligibility_agent.check_eligibility(
            farmer_info=farmer_info,
            explain_decisions=explain_decisions
        )
        
        logger.info(f"Eligibility check completed: {result.eligible_count} eligible schemes")
        return result
        
    except EligibilityCheckError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in eligibility check: {str(e)}")
        raise_eligibility_error(
            "Failed to check eligibility",
            {"error": str(e)}
        )

@router.get("/search", response_model=List[VectorSearchResult])
async def search_schemes(
    query: str = Query(..., description="Search query for schemes"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results to return"),
    similarity_threshold: float = Query(0.5, ge=0.0, le=1.0, description="Minimum similarity score"),
    state: Optional[str] = Query(None, description="Filter by state"),
    vector_db_agent = Depends(get_vector_db_agent)
):
    """
    Search for government schemes using vector similarity
    
    - **query**: Natural language query describing farmer needs
    - **top_k**: Maximum number of schemes to return (1-20)
    - **similarity_threshold**: Minimum similarity score (0.0-1.0)
    - **state**: Optional state filter
    
    Returns list of relevant schemes with similarity scores
    """
    logger.info(f"Searching schemes for query: {query}")
    
    try:
        # Prepare filters
        filters = {}
        if state:
            filters["state"] = state
        
        # Search schemes
        results = await vector_db_agent.search_schemes(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters if filters else None
        )
        
        logger.info(f"Found {len(results)} schemes matching query")
        return results
        
    except VectorDatabaseError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in scheme search: {str(e)}")
        raise_vector_db_error(
            "Failed to search schemes",
            {"error": str(e)}
        )

@router.get("/by-category/{category}")
async def get_schemes_by_category(
    category: str,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    vector_db_agent = Depends(get_vector_db_agent)
):
    """
    Get schemes by category (e.g., 'subsidy', 'loan', 'insurance')
    """
    try:
        schemes = await vector_db_agent.get_schemes_by_category(
            category=category,
            limit=limit,
            offset=offset
        )
        
        return {
            "category": category,
            "schemes": schemes,
            "total_count": len(schemes),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting schemes by category: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get schemes by category")

@router.get("/{scheme_id}", response_model=GovernmentScheme)
async def get_scheme_details(
    scheme_id: str,
    vector_db_agent = Depends(get_vector_db_agent)
):
    """
    Get detailed information about a specific scheme
    
    - **scheme_id**: Unique identifier for the scheme
    """
    logger.info(f"Fetching details for scheme: {scheme_id}")
    
    try:
        scheme = await vector_db_agent.get_scheme_by_id(scheme_id)
        
        if not scheme:
            raise HTTPException(
                status_code=404,
                detail=f"Scheme with ID '{scheme_id}' not found"
            )
        
        return scheme
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scheme details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scheme details")

@router.get("/")
async def list_schemes(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state: Optional[str] = Query(None),
    active_only: bool = Query(True),
    vector_db_agent = Depends(get_vector_db_agent)
):
    """
    List all available government schemes with pagination
    
    - **limit**: Number of schemes to return (1-100)
    - **offset**: Number of schemes to skip
    - **state**: Filter by state (optional)
    - **active_only**: Show only active schemes
    """
    try:
        filters = {"is_active": True} if active_only else {}
        if state:
            filters["state"] = state
        
        schemes = await vector_db_agent.list_schemes(
            limit=limit,
            offset=offset,
            filters=filters
        )
        
        total_count = await vector_db_agent.count_schemes(filters)
        
        return {
            "schemes": schemes,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count
        }
        
    except Exception as e:
        logger.error(f"Error listing schemes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list schemes")

@router.post("/recommend")
async def recommend_schemes(
    farmer_info: FarmerInfo,
    max_recommendations: int = Query(5, ge=1, le=10),
    eligibility_agent = Depends(get_eligibility_agent),
    vector_db_agent = Depends(get_vector_db_agent)
):
    """
    Get personalized scheme recommendations for a farmer
    
    Combines eligibility checking with similarity search
    """
    logger.info("Generating scheme recommendations")
    
    try:
        # Check eligibility first
        eligibility_result = await eligibility_agent.check_eligibility(
            farmer_info=farmer_info,
            explain_decisions=False
        )
        
        # Get eligible schemes
        eligible_schemes = eligibility_result.eligible_schemes[:max_recommendations]
        
        # If we need more recommendations, use similarity search
        if len(eligible_schemes) < max_recommendations:
            # Create search query from farmer info
            query_parts = []
            if farmer_info.crops:
                query_parts.append(f"crops: {', '.join(farmer_info.crops)}")
            if farmer_info.state:
                query_parts.append(f"state: {farmer_info.state}")
            if farmer_info.land_size_acres:
                query_parts.append(f"land size: {farmer_info.land_size_acres} acres")
            
            search_query = " ".join(query_parts) or "general farming support"
            
            # Search for similar schemes
            similar_schemes = await vector_db_agent.search_schemes(
                query=search_query,
                top_k=max_recommendations - len(eligible_schemes),
                similarity_threshold=0.3
            )
            
            # Add similar schemes to recommendations
            for scheme_result in similar_schemes:
                if scheme_result.chunk_id not in [es.scheme_id for es in eligible_schemes]:
                    eligible_schemes.append(EligibilityCheck(
                        scheme_id=scheme_result.chunk_id,
                        scheme_name=scheme_result.metadata.get("name", "Unknown"),
                        status="eligible",  # Assuming eligible based on similarity
                        score=scheme_result.similarity_score,
                        explanation=f"Recommended based on similarity (score: {scheme_result.similarity_score:.2f})"
                    ))
        
        return {
            "farmer_info": farmer_info,
            "recommendations": eligible_schemes[:max_recommendations],
            "total_eligible_schemes": eligibility_result.eligible_count,
            "recommendation_strategy": "eligibility_first_then_similarity"
        }
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate recommendations")

@router.post("/refresh", include_in_schema=False)
async def refresh_schemes(
    background_tasks: BackgroundTasks,
    scraper_agent = Depends(get_scraper_agent),
    vector_db_agent = Depends(get_vector_db_agent)
):
    """
    Refresh scheme database by scraping latest information
    
    This is an admin endpoint and may take several minutes to complete
    """
    logger.info("Starting scheme database refresh")
    
    try:
        # Start refresh in background
        background_tasks.add_task(
            refresh_schemes_background,
            scraper_agent,
            vector_db_agent
        )
        
        return {
            "message": "Scheme refresh started in background",
            "estimated_duration_minutes": 10
        }
        
    except Exception as e:
        logger.error(f"Error starting scheme refresh: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start scheme refresh")

@router.get("/stats/summary")
async def get_scheme_statistics(vector_db_agent = Depends(get_vector_db_agent)):
    """
    Get summary statistics about available schemes
    """
    try:
        stats = await vector_db_agent.get_scheme_statistics()
        
        return {
            "total_schemes": stats.get("total_schemes", 0),
            "active_schemes": stats.get("active_schemes", 0),
            "schemes_by_category": stats.get("by_category", {}),
            "schemes_by_state": stats.get("by_state", {}),
            "last_updated": stats.get("last_updated"),
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error getting scheme statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get scheme statistics")

# Background Tasks

async def refresh_schemes_background(scraper_agent, vector_db_agent):
    """Background task to refresh scheme database"""
    try:
        logger.info("Starting background scheme refresh")
        
        # Scrape latest schemes
        new_schemes = await scraper_agent.scrape_government_schemes()
        logger.info(f"Scraped {len(new_schemes)} schemes")
        
        # Update vector database
        await vector_db_agent.update_schemes(new_schemes)
        logger.info("Scheme database updated successfully")
        
    except Exception as e:
        logger.error(f"Error in background scheme refresh: {str(e)}")

# Export router
__all__ = ["router"]