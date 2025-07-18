"""
EFR Database Integration for Schemabot

This module provides integration with the EFR database scheme service,
replacing the local YAML file loading with API-based scheme retrieval.
"""

import logging
import requests
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json

from .models import GovernmentScheme, SchemeInfo

logger = logging.getLogger(__name__)

class EFRSchemeClient:
    """Client for connecting to EFR database scheme service."""
    
    def __init__(self, efr_api_url: str = "http://localhost:8001"):
        """
        Initialize EFR scheme client.
        
        Args:
            efr_api_url: Base URL for EFR database API
        """
        self.efr_api_url = efr_api_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.schemes_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamp: Optional[datetime] = None
        self.cache_ttl: timedelta = timedelta(minutes=30)  # 30-minute cache
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
        
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if not self.cache_timestamp:
            return False
        return datetime.utcnow() - self.cache_timestamp < self.cache_ttl
        
    async def _fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Fetch data from API with retry logic."""
        session = await self._get_session()
        
        for attempt in range(max_retries):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"API request failed with status {response.status}: {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries} for {url}")
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}/{max_retries} for {url}: {e}")
                
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        logger.error(f"Failed to fetch data after {max_retries} attempts: {url}")
        return None
        
    async def health_check(self) -> Dict[str, Any]:
        """Check if EFR database is healthy and reachable."""
        try:
            result = await self._fetch_with_retry(f"{self.efr_api_url}/health")
            if result:
                return {
                    "status": "healthy",
                    "efr_available": True,
                    "message": "EFR database is reachable"
                }
            else:
                return {
                    "status": "unhealthy",
                    "efr_available": False,
                    "message": "EFR database is not reachable"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "efr_available": False,
                "message": f"Health check failed: {e}"
            }
            
    async def get_schemes_registry(self) -> Optional[Dict[str, Any]]:
        """Get the complete schemes registry from EFR."""
        try:
            url = f"{self.efr_api_url}/api/schemes/registry"
            result = await self._fetch_with_retry(url)
            
            if result and "success" in result and result["success"]:
                logger.info("Successfully fetched schemes registry from EFR")
                return result.get("data", {})
            else:
                logger.error(f"Failed to fetch schemes registry: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching schemes registry: {e}")
            return None
            
    async def list_schemes(self, limit: int = 100, offset: int = 0) -> Optional[List[Dict[str, Any]]]:
        """List all available schemes from EFR."""
        try:
            url = f"{self.efr_api_url}/api/schemes?limit={limit}&offset={offset}"
            result = await self._fetch_with_retry(url)
            
            if result and "success" in result and result["success"]:
                schemes_data = result.get("data", {}).get("schemes", [])
                logger.info(f"Successfully fetched {len(schemes_data)} schemes from EFR")
                return schemes_data
            else:
                logger.error(f"Failed to list schemes: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error listing schemes: {e}")
            return None
            
    async def get_scheme(self, scheme_code: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get a specific scheme definition from EFR."""
        try:
            # Check cache first
            if use_cache and self._is_cache_valid() and scheme_code in self.schemes_cache:
                logger.debug(f"Using cached scheme data for {scheme_code}")
                return self.schemes_cache[scheme_code]
                
            url = f"{self.efr_api_url}/api/schemes/{scheme_code}"
            result = await self._fetch_with_retry(url)
            
            if result and "success" in result and result["success"]:
                scheme_data = result.get("data")
                if scheme_data:
                    # Update cache
                    if use_cache:
                        self.schemes_cache[scheme_code] = scheme_data
                        self.cache_timestamp = datetime.utcnow()
                        
                    logger.info(f"Successfully fetched scheme {scheme_code} from EFR")
                    return scheme_data
                else:
                    logger.warning(f"No scheme data found for {scheme_code}")
                    return None
            else:
                logger.error(f"Failed to get scheme {scheme_code}: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting scheme {scheme_code}: {e}")
            return None
            
    async def get_scheme_data_model(self, scheme_code: str) -> Optional[Dict[str, Any]]:
        """Get the data model for a specific scheme."""
        try:
            url = f"{self.efr_api_url}/api/schemes/{scheme_code}/data-model"
            result = await self._fetch_with_retry(url)
            
            if result:
                logger.info(f"Successfully fetched data model for {scheme_code}")
                return result
            else:
                logger.error(f"Failed to get data model for {scheme_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting data model for {scheme_code}: {e}")
            return None
            
    async def get_scheme_eligibility_rules(self, scheme_code: str) -> Optional[List[Dict[str, Any]]]:
        """Get eligibility rules for a specific scheme."""
        try:
            url = f"{self.efr_api_url}/api/schemes/{scheme_code}/eligibility-rules"
            result = await self._fetch_with_retry(url)
            
            if result:
                logger.info(f"Successfully fetched eligibility rules for {scheme_code}")
                return result.get("eligibility_rules", [])
            else:
                logger.error(f"Failed to get eligibility rules for {scheme_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting eligibility rules for {scheme_code}: {e}")
            return None
            
    async def validate_farmer_data(self, scheme_code: str, farmer_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate farmer data against a scheme's data model."""
        try:
            url = f"{self.efr_api_url}/api/schemes/{scheme_code}/validate"
            session = await self._get_session()
            
            async with session.post(
                url, 
                json=farmer_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Successfully validated farmer data for {scheme_code}")
                    return result
                else:
                    logger.error(f"Validation failed with status {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error validating farmer data for {scheme_code}: {e}")
            return None
            
    async def get_scheme_stats(self) -> Optional[Dict[str, Any]]:
        """Get statistics about all schemes."""
        try:
            url = f"{self.efr_api_url}/api/schemes/stats"
            result = await self._fetch_with_retry(url)
            
            if result:
                logger.info("Successfully fetched scheme statistics")
                return result
            else:
                logger.error("Failed to get scheme statistics")
                return None
                
        except Exception as e:
            logger.error(f"Error getting scheme statistics: {e}")
            return None
            
    def clear_cache(self):
        """Clear the schemes cache."""
        self.schemes_cache.clear()
        self.cache_timestamp = None
        logger.info("Schemes cache cleared")


class EFRSchemeParser:
    """
    Enhanced SchemeParser that uses EFR database as source of truth.
    
    This replaces the local YAML file loading with API-based scheme retrieval
    from the EFR database, providing access to enhanced canonical schemes.
    """
    
    def __init__(self, efr_api_url: str = "http://localhost:8001"):
        """
        Initialize EFR-based scheme parser.
        
        Args:
            efr_api_url: Base URL for EFR database API
        """
        self.efr_client = EFRSchemeClient(efr_api_url)
        self.schemes: Dict[str, GovernmentScheme] = {}
        self.validation_errors: Dict[str, List[str]] = {}
        self.parsing_errors: List[str] = []
        self.last_loaded: Optional[datetime] = None
        
    async def load_schemes(self) -> bool:
        """Load schemes from EFR database."""
        try:
            logger.info("Loading schemes from EFR database...")
            
            # Check EFR health first
            async with self.efr_client as client:
                health = await client.health_check()
                if not health.get("efr_available", False):
                    error_msg = f"EFR database not available: {health.get('message', 'Unknown error')}"
                    self.parsing_errors.append(error_msg)
                    logger.error(error_msg)
                    return False
                
                # Get list of schemes
                schemes_data = await client.list_schemes()
                if not schemes_data:
                    error_msg = "No schemes data received from EFR database"
                    self.parsing_errors.append(error_msg)
                    logger.error(error_msg)
                    return False
                
                schemes_loaded = 0
                for scheme_data in schemes_data:
                    try:
                        # Convert EFR scheme data to GovernmentScheme
                        scheme = await self._convert_efr_scheme(scheme_data)
                        self.schemes[scheme.code] = scheme
                        schemes_loaded += 1
                        logger.debug(f"Successfully loaded scheme: {scheme.code}")
                        
                    except Exception as e:
                        error_msg = f"Failed to process scheme {scheme_data.get('code', 'unknown')}: {e}"
                        logger.error(error_msg)
                        self.parsing_errors.append(error_msg)
                        continue
                
                self.last_loaded = datetime.utcnow()
                logger.info(f"Successfully loaded {schemes_loaded} schemes from EFR database")
                return schemes_loaded > 0
                
        except Exception as e:
            error_msg = f"Failed to load schemes from EFR database: {e}"
            self.parsing_errors.append(error_msg)
            logger.error(error_msg)
            return False
            
    async def _convert_efr_scheme(self, efr_scheme_data: Dict[str, Any]) -> GovernmentScheme:
        """Convert EFR scheme data format to GovernmentScheme."""
        try:
            # EFR scheme data has a different structure, so we need to map it
            # to the expected GovernmentScheme format
            
            scheme_data = {
                "id": efr_scheme_data.get("id", ""),
                "name": efr_scheme_data.get("name", ""),
                "code": efr_scheme_data.get("code", ""),
                "description": efr_scheme_data.get("description", ""),
                "ministry": efr_scheme_data.get("ministry", ""),
                "launched_on": efr_scheme_data.get("launched_on", ""),
                "status": efr_scheme_data.get("status", "active"),
                
                # Map eligibility rules
                "eligibility": {
                    "rules": efr_scheme_data.get("eligibility_rules", []),
                    "logic": "ALL"
                },
                
                # Map exclusion criteria
                "exclusion_criteria": efr_scheme_data.get("exclusion_criteria", []),
                
                # Map benefits
                "benefits": efr_scheme_data.get("benefits", []),
                
                # Map documents
                "documents": efr_scheme_data.get("documents", []),
                
                # Map special provisions
                "special_provisions": efr_scheme_data.get("special_provisions", []),
                
                # Metadata
                "metadata": {
                    "source": "efr_database",
                    "last_updated": efr_scheme_data.get("updated_at", ""),
                    "version": efr_scheme_data.get("version", "1.0.0"),
                    "categories": efr_scheme_data.get("categories", []),
                    "tags": efr_scheme_data.get("tags", [])
                }
            }
            
            return GovernmentScheme(**scheme_data)
            
        except Exception as e:
            raise Exception(f"Failed to convert EFR scheme data: {e}")
            
    async def get_scheme(self, code: str) -> Optional[GovernmentScheme]:
        """Get a scheme by code."""
        return self.schemes.get(code)
        
    async def get_required_fields(self, code: str) -> List[str]:
        """Get required fields for a scheme."""
        scheme = await self.get_scheme(code)
        if not scheme:
            return []
            
        # Get required fields from validation rules
        validation_rules = getattr(scheme, 'validation_rules', {})
        if validation_rules and 'required_for_eligibility' in validation_rules:
            return validation_rules['required_for_eligibility']
        
        # Fallback to eligibility rules
        eligibility_rules = getattr(scheme, 'eligibility', {}).get('rules', [])
        return [rule.get('rule_id', rule.get('field', '')) for rule in eligibility_rules if rule.get('is_required', True)]
        
    async def get_field_metadata(self, scheme_code: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific field."""
        try:
            # Use EFR client to get detailed data model
            async with self.efr_client as client:
                data_model = await client.get_scheme_data_model(scheme_code)
                if not data_model:
                    return None
                    
                # Search through data model sections for the field
                for section in data_model.get("data_model", []):
                    fields = section.get("fields", {})
                    if field_name in fields:
                        field_data = fields[field_name]
                        return {
                            "type": field_data.get("type", "string"),
                            "required": field_data.get("required", False),
                            "description": field_data.get("description", ""),
                            "validation": field_data.get("validation", ""),
                            "values": field_data.get("values"),
                            "section": section.get("name", "")
                        }
                        
                return None
                
        except Exception as e:
            logger.error(f"Error getting field metadata for {scheme_code}.{field_name}: {e}")
            return None
            
    async def validate_farmer_data(self, scheme_code: str, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate farmer data using EFR validation."""
        try:
            async with self.efr_client as client:
                result = await client.validate_farmer_data(scheme_code, farmer_data)
                if result:
                    return result
                else:
                    return {
                        "is_valid": False,
                        "errors": ["Failed to validate data using EFR service"],
                        "warnings": []
                    }
                    
        except Exception as e:
            logger.error(f"Error validating farmer data: {e}")
            return {
                "is_valid": False,
                "errors": [f"Validation error: {e}"],
                "warnings": []
            }
            
    def get_parsing_errors(self) -> List[str]:
        """Get any parsing errors that occurred during loading."""
        return self.parsing_errors.copy()
        
    def get_validation_errors(self) -> Dict[str, List[str]]:
        """Get validation errors for schemes."""
        return self.validation_errors.copy() 