#schemabot\api\routes\schemes.py

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Optional
import os
from pathlib import Path
import yaml
from datetime import datetime, timezone

# Fixed imports - use the actual model names from your models.py
from core.scheme.models import GovernmentScheme, Metadata, Monitoring
from core.scheme.parser import SchemeParser
from core.scheme.validitor import SchemeValidator
from api.models.requests import (
    CreateSchemeRequest, 
    UpdateSchemeRequest, 
    ValidateSchemeRequest
)
from api.models.responses import (
    SchemeResponse,
    BaseResponse, 
    ValidationResponse
)
# Create missing models that the code expects
from pydantic import BaseModel, ConfigDict

class SchemeMetadata(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    last_updated: datetime
    version: str
    source_file: str

class SchemeResponse(BaseModel):
    scheme: GovernmentScheme
    metadata: SchemeMetadata

class SchemeListResponse(BaseModel):
    schemes: List[GovernmentScheme]
    total_count: int
    limit: int
    offset: int
    has_more: bool

class ValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str] = []
    scheme_code: str

# Aliases for backward compatibility
Scheme = GovernmentScheme
SchemeStatus = str  # Simple string for now

router = APIRouter(prefix="/schemes", tags=["schemes"])

# Initialize dependencies
scheme_parser = SchemeParser()

BASE_DIR = "/mnt/d/Sanchalak/Sanchalak/schemabot"  # or wherever your base directory is
scheme_validator = SchemeValidator(base_dir=BASE_DIR)


@router.get("/", response_model=SchemeListResponse)
async def list_schemes(
    active_only: bool = Query(True, description="Filter to active schemes only"),
    category: Optional[str] = Query(None, description="Filter by scheme category"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of schemes to return"),
    offset: int = Query(0, ge=0, description="Number of schemes to skip"),
):
    """
    Retrieve a list of all available government schemes.
    Supports filtering by status, category, and pagination.
    """
    try:
        # Check cache first
        cache_key = f"schemes:list:{active_only}:{category}:{limit}:{offset}"
        cached_result = await cache_manager.get(cache_key)

        if cached_result:
            logger.info("Returning cached scheme list")
            return cached_result

        # Load schemes from registry
        schemes_registry_path = Path("schemas/schemes_registry.yaml")
        if not schemes_registry_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schemes registry not found"
            )

        with open(schemes_registry_path, 'r', encoding='utf-8') as f:
            registry = yaml.safe_load(f)

        schemes = []
        for scheme_code, scheme_info in registry.get("schemes", {}).items():
            # Apply filters
            if active_only and scheme_info.get("status") != "active":
                continue

            if category and scheme_info.get("category") != category:
                continue

            # Load full scheme data
            scheme_path = Path(f"schemas/{scheme_info['file']}")
            if scheme_path.exists():
                try:
                    scheme_data = await scheme_parser.parse_scheme(str(scheme_path))
                    schemes.append(scheme_data)
                except Exception as e:
                    logger.warning(f"Failed to parse scheme {scheme_code}: {e}")
                    continue

        # Apply pagination
        total_count = len(schemes)
        schemes = schemes[offset:offset + limit]

        result = SchemeListResponse(
            schemes=schemes,
            total_count=total_count,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total_count
        )

        # Cache the result
        await cache_manager.set(cache_key, result, ttl=300)  # 5 minutes

        # Record metrics
        await metrics_collector.record_api_call("list_schemes", len(schemes))

        return result

    except Exception as e:
        logger.error(f"Failed to list schemes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve schemes"
        )


@router.get("/{scheme_code}", response_model=SchemeResponse)
async def get_scheme(
    scheme_code: str,
    include_rules: bool = Query(True, description="Include eligibility rules")):
    """
    Retrieve detailed information about a specific scheme.
    """
    try:
        # Check cache first
        cache_key = f"scheme:{scheme_code}:{include_rules}"
        cached_result = await cache_manager.get(cache_key)

        if cached_result:
            logger.info(f"Returning cached scheme data for {scheme_code}")
            return cached_result

        # Load scheme from file
        scheme_path = Path(f"schemas/{scheme_code}.yaml")
        if not scheme_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme '{scheme_code}' not found"
            )

        scheme_data = await scheme_parser.parse_scheme(str(scheme_path))

        if not include_rules:
            # Clear eligibility rules if not requested
            scheme_data.eligibility.rules = []

        result = SchemeResponse(
            scheme=scheme_data,
            metadata=SchemeMetadata(
                last_updated=datetime.now(timezone.utc),
                version="1.0",
                source_file=str(scheme_path)
            )
        )

        # Cache the result
        await cache_manager.set(cache_key, result, ttl=600)  # 10 minutes

        # Record metrics
        await metrics_collector.record_api_call("get_scheme", 1)

        return result

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme '{scheme_code}' not found"
        )
    except Exception as e:
        logger.error(f"Failed to get scheme {scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scheme"
        )


@router.post("/", response_model=SchemeResponse)
async def create_scheme(
    request: CreateSchemeRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create a new government scheme.
    Requires admin access and validates scheme data.
    """
    try:
        # Validate scheme data
        validation_result = await scheme_validator.validate_scheme(request.scheme_data)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme validation failed: {validation_result.errors}"
            )

        # Check if scheme already exists
        scheme_path = Path(f"schemas/{request.scheme_code}.yaml")
        if scheme_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Scheme '{request.scheme_code}' already exists"
            )

        # Parse and save scheme
        scheme_data = await scheme_parser.parse_scheme_data(request.scheme_data)

        # Save to file
        with open(scheme_path, 'w', encoding='utf-8') as f:
            yaml.dump(request.scheme_data, f, default_flow_style=False, allow_unicode=True)

        # Update registry
        background_tasks.add_task(update_schemes_registry, request.scheme_code, {
            "file": f"{request.scheme_code}.yaml",
            "status": "active",
            "category": scheme_data.metadata.category,
            "created_by": current_user.username,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        # Clear cache
        await cache_manager.delete_pattern("schemes:*")

        # Record metrics
        await metrics_collector.record_api_call("create_scheme", 1)

        return SchemeResponse(
            scheme=scheme_data,
            metadata=SchemeMetadata(
                last_updated=datetime.now(timezone.utc),
                version="1.0",
                source_file=str(scheme_path)
            )
        )

    except Exception as e:
        logger.error(f"Failed to create scheme {request.scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create scheme"
        )


@router.put("/{scheme_code}", response_model=SchemeResponse)
async def update_scheme(
    scheme_code: str,
    request: UpdateSchemeRequest,
    background_tasks: BackgroundTasks
):
    """
    Update an existing government scheme.
    Requires admin access and validates updated data.
    """
    try:
        # Check if scheme exists
        scheme_path = Path(f"schemas/{scheme_code}.yaml")
        if not scheme_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme '{scheme_code}' not found"
            )

        # Validate updated scheme data
        validation_result = await scheme_validator.validate_scheme(request.scheme_data)
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheme validation failed: {validation_result.errors}"
            )

        # Create backup
        backup_path = Path(f"schemas/backups/{scheme_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml")
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy current file to backup
        import shutil
        shutil.copy2(scheme_path, backup_path)

        # Parse and save updated scheme
        scheme_data = await scheme_parser.parse_scheme_data(request.scheme_data)

        # Save updated file
        with open(scheme_path, 'w', encoding='utf-8') as f:
            yaml.dump(request.scheme_data, f, default_flow_style=False, allow_unicode=True)

        # Update registry
        background_tasks.add_task(update_schemes_registry, scheme_code, {
            "file": f"{scheme_code}.yaml",
            "status": "active",
            "category": scheme_data.metadata.category,
            "updated_by": current_user.username,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

        # Clear cache
        await cache_manager.delete_pattern("schemes:*")
        await cache_manager.delete_pattern(f"scheme:{scheme_code}:*")

        # Record metrics
        await metrics_collector.record_api_call("update_scheme", 1)

        return SchemeResponse(
            scheme=scheme_data,
            metadata=SchemeMetadata(
                last_updated=datetime.now(timezone.utc),
                version="1.1",
                source_file=str(scheme_path)
            )
        )

    except Exception as e:
        logger.error(f"Failed to update scheme {scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update scheme"
        )


@router.delete("/{scheme_code}")
async def delete_scheme(
    scheme_code: str
):
    """
    Delete a government scheme.
    Requires admin access and creates backup before deletion.
    """
    try:
        # Check if scheme exists
        scheme_path = Path(f"schemas/{scheme_code}.yaml")
        if not scheme_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme '{scheme_code}' not found"
            )

        # Create backup before deletion
        backup_path = Path(f"schemas/deleted/{scheme_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml")
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.move(str(scheme_path), str(backup_path))

        # Update registry to mark as deleted
        await update_schemes_registry(scheme_code, {
            "status": "deleted",
            "deleted_by": current_user.username,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "backup_file": str(backup_path)
        })

        # Clear cache
        await cache_manager.delete_pattern("schemes:*")
        await cache_manager.delete_pattern(f"scheme:{scheme_code}:*")

        # Record metrics
        await metrics_collector.record_api_call("delete_scheme", 1)

        return {"message": f"Scheme '{scheme_code}' deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete scheme {scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete scheme"
        )


@router.post("/{scheme_code}/validate", response_model=ValidationResponse)
async def validate_scheme(
    scheme_code: str,
    request: ValidateSchemeRequest):
    """
    Validate a scheme's structure and rules.
    """
    try:
        # Load scheme data
        if request.scheme_data:
            # Validate provided data
            validation_result = await scheme_validator.validate_scheme(request.scheme_data)
        else:
            # Validate existing scheme file
            scheme_path = Path(f"schemas/{scheme_code}.yaml")
            if not scheme_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Scheme '{scheme_code}' not found"
                )

            with open(scheme_path, 'r', encoding='utf-8') as f:
                scheme_data = yaml.safe_load(f)

            validation_result = await scheme_validator.validate_scheme(scheme_data)

        # Record metrics
        await metrics_collector.record_api_call("validate_scheme", 1)

        return ValidationResponse(
            is_valid=validation_result.is_valid,
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            scheme_code=scheme_code
        )

    except Exception as e:
        logger.error(f"Failed to validate scheme {scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate scheme"
        )


@router.get("/{scheme_code}/export")
async def export_scheme(
    scheme_code: str,
    format: str = Query("yaml", pattern="^(yaml|json)$", description="Export format"),  # Fixed: regex → pattern
):
    """
    Export a scheme in the specified format.
    """
    try:
        scheme_path = Path(f"schemas/{scheme_code}.yaml")
        if not scheme_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheme '{scheme_code}' not found"
            )

        if format == "yaml":
            return FileResponse(
                str(scheme_path),
                media_type="application/x-yaml",
                filename=f"{scheme_code}.yaml"
            )
        elif format == "json":
            # Convert YAML to JSON
            with open(scheme_path, 'r', encoding='utf-8') as f:
                scheme_data = yaml.safe_load(f)

            import json
            json_path = Path(f"temp/{scheme_code}.json")
            json_path.parent.mkdir(parents=True, exist_ok=True)

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(scheme_data, f, indent=2, ensure_ascii=False)

            return FileResponse(
                str(json_path),
                media_type="application/json",
                filename=f"{scheme_code}.json"
            )

    except Exception as e:
        logger.error(f"Failed to export scheme {scheme_code}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export scheme"
        )


async def update_schemes_registry(scheme_code: str, scheme_info: Dict[str, Any]):
    """
    Update the schemes registry with new or updated scheme information.
    """
    try:
        registry_path = Path("schemas/schemes_registry.yaml")

        # Load existing registry
        if registry_path.exists():
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = yaml.safe_load(f) or {}
        else:
            registry = {}

        # Update scheme info
        if "schemes" not in registry:
            registry["schemes"] = {}

        registry["schemes"][scheme_code] = scheme_info

        # Save updated registry
        with open(registry_path, 'w', encoding='utf-8') as f:
            yaml.dump(registry, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Updated schemes registry for {scheme_code}")

    except Exception as e:
        logger.error(f"Failed to update schemes registry: {e}")
