"""
EFR Database MCP Tools

Provides tools for LLMs to interact with the Enhanced Farmer Registry database.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
import os

# Add pipeline path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from efr_storage import EFRStorage

logger = logging.getLogger(__name__)

class EFRTools:
    """MCP tools for EFR database interaction."""
    
    def __init__(self, efr_api_url: str = "http://localhost:8000"):
        """Initialize EFR tools."""
        self.efr_storage = EFRStorage(efr_api_url)
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of MCP tools for EFR operations."""
        return [
            {
                "name": "efr_get_farmer",
                "description": "Get farmer data from EFR database by farmer ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_id": {
                            "type": "string",
                            "description": "Unique identifier for the farmer"
                        }
                    },
                    "required": ["farmer_id"]
                }
            },
            {
                "name": "efr_search_farmers",
                "description": "Search farmers in EFR database by various criteria",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Farmer name to search for"
                        },
                        "state": {
                            "type": "string", 
                            "description": "State to filter by"
                        },
                        "district": {
                            "type": "string",
                            "description": "District to filter by"
                        },
                        "crops": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Crops to filter by"
                        },
                        "land_size_min": {
                            "type": "number",
                            "description": "Minimum land size in acres"
                        },
                        "land_size_max": {
                            "type": "number", 
                            "description": "Maximum land size in acres"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 100
                        }
                    }
                }
            },
            {
                "name": "efr_add_farmer",
                "description": "Add a new farmer to EFR database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_data": {
                            "type": "object",
                            "description": "Farmer data dictionary with all fields"
                        }
                    },
                    "required": ["farmer_data"]
                }
            },
            {
                "name": "efr_update_farmer",
                "description": "Update existing farmer data in EFR database",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_id": {
                            "type": "string",
                            "description": "Unique identifier for the farmer"
                        },
                        "farmer_data": {
                            "type": "object",
                            "description": "Updated farmer data"
                        }
                    },
                    "required": ["farmer_id", "farmer_data"]
                }
            },
            {
                "name": "efr_get_summary",
                "description": "Get summary statistics from EFR database",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "efr_list_farmers",
                "description": "List farmers from EFR database with optional filtering",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of farmers to return",
                            "default": 100
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Number of farmers to skip",
                            "default": 0
                        },
                        "state": {
                            "type": "string",
                            "description": "Filter by state"
                        },
                        "district": {
                            "type": "string",
                            "description": "Filter by district"
                        }
                    }
                }
            }
        ]
    
    def efr_get_farmer(self, farmer_id: str) -> Dict[str, Any]:
        """Get farmer data from EFR database."""
        try:
            farmer_data = self.efr_storage.get_farmer(farmer_id)
            if farmer_data:
                return {
                    "success": True,
                    "data": farmer_data,
                    "message": f"Retrieved farmer {farmer_id}"
                }
            else:
                return {
                    "success": False,
                    "message": f"Farmer {farmer_id} not found"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to get farmer {farmer_id}"
            }
    
    def efr_search_farmers(self, **search_criteria) -> Dict[str, Any]:
        """Search farmers in EFR database."""
        try:
            # Clean up search criteria
            clean_criteria = {}
            for key, value in search_criteria.items():
                if value is not None and value != "":
                    clean_criteria[key] = value
            
            farmers = self.efr_storage.search_farmers(clean_criteria)
            return {
                "success": True,
                "data": farmers,
                "count": len(farmers),
                "message": f"Found {len(farmers)} farmers matching criteria"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to search farmers"
            }
    
    def efr_add_farmer(self, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new farmer to EFR database."""
        try:
            result = self.efr_storage.add_farmer(farmer_data)
            return {
                "success": result.get("success", False),
                "data": result.get("data"),
                "message": result.get("message", "Unknown result"),
                "error": result.get("error")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to add farmer"
            }
    
    def efr_update_farmer(self, farmer_id: str, farmer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing farmer data in EFR database."""
        try:
            result = self.efr_storage.update_farmer(farmer_id, farmer_data)
            return {
                "success": result.get("success", False),
                "data": result.get("data"),
                "message": result.get("message", "Unknown result"),
                "error": result.get("error")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to update farmer {farmer_id}"
            }
    
    def efr_get_summary(self) -> Dict[str, Any]:
        """Get summary statistics from EFR database."""
        try:
            summary = self.efr_storage.get_summary()
            if summary:
                return {
                    "success": True,
                    "data": summary,
                    "message": "Retrieved EFR summary"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to get summary"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get summary"
            }
    
    def efr_list_farmers(self, **filters) -> Dict[str, Any]:
        """List farmers from EFR database with optional filtering."""
        try:
            # Extract limit and offset
            limit = filters.pop("limit", 100)
            offset = filters.pop("offset", 0)
            
            # Clean up other filters
            clean_filters = {}
            for key, value in filters.items():
                if value is not None and value != "":
                    clean_filters[key] = value
            
            farmers = self.efr_storage.list_farmers(limit=limit, offset=offset, **clean_filters)
            return {
                "success": True,
                "data": farmers,
                "count": len(farmers),
                "limit": limit,
                "offset": offset,
                "message": f"Retrieved {len(farmers)} farmers"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to list farmers"
            } 