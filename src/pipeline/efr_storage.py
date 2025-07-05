"""
EFR Storage Module

Handles storage and retrieval of farmer data in the EFR (Enhanced Farmer Registry) database.
References the existing EFR database from new/src/efr_database.
"""

import requests
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class EFRStorage:
    """Handles EFR database operations."""
    
    def __init__(self, efr_api_url: str = "http://localhost:8000"):
        """
        Initialize EFR storage client.
        
        Args:
            efr_api_url: URL of the EFR database API
        """
        self.api_url = efr_api_url.rstrip('/')
        self.session = requests.Session()
        
    def health_check(self) -> bool:
        """Check if EFR database is healthy."""
        try:
            response = self.session.get(f"{self.api_url}/health")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ EFR Database healthy: {data.get('total_farmers', 0)} farmers")
                return True
            else:
                logger.error(f"❌ EFR Database unhealthy: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ EFR Database connection failed: {str(e)}")
            return False
    
    def add_farmer(self, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a farmer to the EFR database.
        
        Args:
            farmer_data: Farmer data dictionary
            
        Returns:
            Response from the EFR API
        """
        try:
            logger.info(f"Adding farmer {farmer_data.get('farmer_id', 'unknown')} to EFR")
            
            response = self.session.post(
                f"{self.api_url}/add_farmer",
                json=farmer_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"✅ Farmer added successfully: {farmer_data.get('farmer_id')}")
                    return result
                else:
                    logger.warning(f"⚠️ Farmer add failed: {result.get('message')}")
                    return result
            else:
                logger.error(f"❌ EFR API error: {response.status_code}")
                return {
                    "success": False,
                    "message": f"API error: {response.status_code}",
                    "error": response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to add farmer: {str(e)}")
            return {
                "success": False,
                "message": "Connection error",
                "error": str(e)
            }
    
    def get_farmer(self, farmer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a farmer from the EFR database.
        
        Args:
            farmer_id: Unique identifier for the farmer
            
        Returns:
            Farmer data dictionary or None if not found
        """
        try:
            response = self.session.get(f"{self.api_url}/farmer/{farmer_id}")
            
            if response.status_code == 200:
                farmer_data = response.json()
                logger.info(f"✅ Retrieved farmer {farmer_id}")
                return farmer_data
            elif response.status_code == 404:
                logger.warning(f"⚠️ Farmer {farmer_id} not found")
                return None
            else:
                logger.error(f"❌ EFR API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get farmer {farmer_id}: {str(e)}")
            return None
    
    def update_farmer(self, farmer_id: str, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a farmer in the EFR database.
        
        Args:
            farmer_id: Unique identifier for the farmer
            farmer_data: Updated farmer data
            
        Returns:
            Response from the EFR API
        """
        try:
            logger.info(f"Updating farmer {farmer_id}")
            
            response = self.session.put(
                f"{self.api_url}/farmer/{farmer_id}",
                json=farmer_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"✅ Farmer updated successfully: {farmer_id}")
                    return result
                else:
                    logger.warning(f"⚠️ Farmer update failed: {result.get('message')}")
                    return result
            else:
                logger.error(f"❌ EFR API error: {response.status_code}")
                return {
                    "success": False,
                    "message": f"API error: {response.status_code}",
                    "error": response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to update farmer {farmer_id}: {str(e)}")
            return {
                "success": False,
                "message": "Connection error",
                "error": str(e)
            }
    
    def search_farmers(self, search_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search farmers in the EFR database.
        
        Args:
            search_criteria: Search criteria dictionary
            
        Returns:
            List of matching farmers
        """
        try:
            response = self.session.post(
                f"{self.api_url}/search",
                json=search_criteria,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                farmers = response.json()
                logger.info(f"✅ Found {len(farmers)} farmers matching criteria")
                return farmers
            else:
                logger.error(f"❌ EFR API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to search farmers: {str(e)}")
            return []
    
    def list_farmers(self, limit: int = 100, offset: int = 0, **filters) -> List[Dict[str, Any]]:
        """
        List farmers from the EFR database with optional filtering.
        
        Args:
            limit: Maximum number of farmers to return
            offset: Number of farmers to skip
            **filters: Additional filter parameters
            
        Returns:
            List of farmers
        """
        try:
            params = {"limit": limit, "offset": offset}
            params.update(filters)
            
            response = self.session.get(f"{self.api_url}/farmers", params=params)
            
            if response.status_code == 200:
                farmers = response.json()
                logger.info(f"✅ Retrieved {len(farmers)} farmers")
                return farmers
            else:
                logger.error(f"❌ EFR API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to list farmers: {str(e)}")
            return []
    
    def get_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get summary statistics from the EFR database.
        
        Returns:
            Summary statistics dictionary
        """
        try:
            response = self.session.get(f"{self.api_url}/summary")
            
            if response.status_code == 200:
                summary = response.json()
                logger.info(f"✅ Retrieved EFR summary: {summary.get('total_farmers', 0)} farmers")
                return summary
            else:
                logger.error(f"❌ EFR API error: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get summary: {str(e)}")
            return None 