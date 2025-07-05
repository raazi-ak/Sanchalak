"""
MCP Server for Sanchalak

Provides Model Context Protocol tools for LLMs to interact with:
- EFR Database
- Prolog Eligibility System  
- Data Processing Pipeline
- Clarification Workflow
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import sys
import os

# Add mcp_tools path
sys.path.append(os.path.join(os.path.dirname(__file__), 'mcp_tools'))
from mcp_tools import EFRTools, PrologTools, DataTools
from mcp_tools.clarification_workflow import ClarificationWorkflow
from mcp_tools.canonical_scheme_tools import CanonicalSchemeTools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SanchalakMCPServer:
    """MCP Server for Sanchalak system."""
    
    def __init__(self, 
                 efr_api_url: str = "http://localhost:8000",
                 lm_studio_url: str = "http://localhost:1234/v1",
                 prolog_file_path: str = None,
                 canonical_schemes_directory: str = "src/schemes/outputs"):
        """
        Initialize the MCP server.
        
        Args:
            efr_api_url: URL for EFR database API
            lm_studio_url: URL for LM Studio API
            prolog_file_path: Path to Prolog eligibility system file
            canonical_schemes_directory: Path to canonical schemes directory
        """
        self.efr_tools = EFRTools(efr_api_url)
        self.prolog_tools = PrologTools(prolog_file_path)
        self.data_tools = DataTools(lm_studio_url)
        self.clarification_workflow = ClarificationWorkflow(lm_studio_url)
        self.canonical_scheme_tools = CanonicalSchemeTools(canonical_schemes_directory)
        
        # Combine all tools
        self.all_tools = {}
        self._register_tools()
        
    def _register_tools(self):
        """Register all available tools."""
        # EFR tools
        for tool in self.efr_tools.get_tools():
            self.all_tools[tool["name"]] = {
                "tool": tool,
                "handler": getattr(self.efr_tools, tool["name"])
            }
        
        # Prolog tools
        for tool in self.prolog_tools.get_tools():
            self.all_tools[tool["name"]] = {
                "tool": tool,
                "handler": getattr(self.prolog_tools, tool["name"])
            }
        
        # Data tools
        for tool in self.data_tools.get_tools():
            self.all_tools[tool["name"]] = {
                "tool": tool,
                "handler": getattr(self.data_tools, tool["name"])
            }
        
        # Clarification workflow tools
        for tool in self.clarification_workflow.get_tools():
            self.all_tools[tool["name"]] = {
                "tool": tool,
                "handler": getattr(self.clarification_workflow, tool["name"])
            }
        
        # Canonical scheme tools
        for tool in self.canonical_scheme_tools.get_tools():
            self.all_tools[tool["name"]] = {
                "tool": tool,
                "handler": getattr(self.canonical_scheme_tools, tool["name"])
            }
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools."""
        return [tool_info["tool"] for tool_info in self.all_tools.values()]
    
    def execute_tool(self, tool_name: str, **parameters) -> Dict[str, Any]:
        """
        Execute a tool by name with parameters.
        
        Args:
            tool_name: Name of the tool to execute
            **parameters: Tool parameters
            
        Returns:
            Tool execution result
        """
        if tool_name not in self.all_tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "available_tools": list(self.all_tools.keys())
            }
        
        try:
            tool_info = self.all_tools[tool_name]
            handler = tool_info["handler"]
            
            # Execute the tool
            result = handler(**parameters)
            
            # Add tool metadata
            result["tool_name"] = tool_name
            result["executed_at"] = datetime.utcnow().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "message": f"Failed to execute {tool_name}"
            }
    
    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Get information about a specific tool."""
        if tool_name not in self.all_tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found"
            }
        
        return {
            "success": True,
            "tool": self.all_tools[tool_name]["tool"]
        }
    
    def list_tools(self) -> Dict[str, Any]:
        """List all available tools with descriptions."""
        tools_info = []
        for tool_name, tool_info in self.all_tools.items():
            tool = tool_info["tool"]
            tools_info.append({
                "name": tool_name,
                "description": tool.get("description", "No description"),
                "parameters": tool.get("parameters", {})
            })
        
        return {
            "success": True,
            "tools": tools_info,
            "count": len(tools_info),
                            "categories": {
                    "efr_tools": len([t for t in tools_info if t["name"].startswith("efr_")]),
                    "prolog_tools": len([t for t in tools_info if t["name"].startswith("prolog_")]),
                    "canonical_scheme_tools": len([t for t in tools_info if t["name"] in ["list_available_schemes", "get_scheme_details", "get_field_definitions", "generate_consent_request", "validate_collected_data", "get_field_prompt_examples"]]),
                    "data_tools": len([t for t in tools_info if not t["name"].startswith(("efr_", "prolog_", "start_clarification", "get_next_clarification", "submit_clarification", "check_clarification", "finalize_clarification", "get_clarification")) and t["name"] not in ["list_available_schemes", "get_scheme_details", "get_field_definitions", "generate_consent_request", "validate_collected_data", "get_field_prompt_examples"]]),
                    "clarification_tools": len([t for t in tools_info if t["name"].startswith(("start_clarification", "get_next_clarification", "submit_clarification", "check_clarification", "finalize_clarification", "get_clarification"))])
                }
        }
    
    def run_canonical_workflow(self, scheme_code: str, farmer_id: str) -> Dict[str, Any]:
        """
        Run the canonical workflow using MCP tools.
        
        Args:
            scheme_code: Code of the scheme to check eligibility for
            farmer_id: Unique identifier for the farmer
            
        Returns:
            Complete workflow result
        """
        workflow_steps = []
        
        try:
            # Step 1: Get scheme details
            logger.info(f"Step 1: Getting scheme details for {scheme_code}")
            scheme_result = await self.execute_tool("get_scheme_details", scheme_code=scheme_code)
            workflow_steps.append({"step": "get_scheme_details", "result": scheme_result})
            
            if not scheme_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to get scheme details for {scheme_code}",
                    "workflow_steps": workflow_steps
                }
            
            # Step 2: Generate consent request
            logger.info(f"Step 2: Generating consent request for {scheme_code}")
            consent_result = await self.execute_tool("generate_consent_request", scheme_code=scheme_code)
            workflow_steps.append({"step": "generate_consent", "result": consent_result})
            
            if not consent_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to generate consent request",
                    "workflow_steps": workflow_steps
                }
            
            # Step 3: Get field definitions for data collection
            logger.info(f"Step 3: Getting field definitions for {scheme_code}")
            fields_result = await self.execute_tool("get_field_definitions", scheme_code=scheme_code)
            workflow_steps.append({"step": "get_field_definitions", "result": fields_result})
            
            if not fields_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to get field definitions",
                    "workflow_steps": workflow_steps
                }
            
            return {
                "success": True,
                "scheme_code": scheme_code,
                "farmer_id": farmer_id,
                "consent_text": consent_result.get("consent_text"),
                "field_definitions": fields_result.get("fields_by_section"),
                "required_fields": fields_result.get("required_fields"),
                "workflow_steps": workflow_steps,
                "message": f"Canonical workflow initialized for {scheme_code}"
            }
            
        except Exception as e:
            logger.error(f"Canonical workflow error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "workflow_steps": workflow_steps,
                "message": "Canonical workflow failed"
            }

# Example usage and testing
def main():
    """Example usage of the MCP server."""
    server = SanchalakMCPServer()
    
    print("=== Sanchalak MCP Server ===")
    print(f"Available tools: {len(server.get_tools())}")
    
    # List all tools
    tools_list = server.list_tools()
    print(f"\nTools by category:")
    for category, count in tools_list["categories"].items():
        print(f"  {category}: {count} tools")
    
    print(f"\nAll tools:")
    for tool in tools_list["tools"]:
        print(f"  - {tool['name']}: {tool['description']}")
    
    # Example: Run complete workflow
    print(f"\n=== Example: Complete Workflow ===")
    sample_transcript = """
    My name is Ramesh Kumar. I am 45 years old and I live in Karnataka. 
    I have some land but I'm not sure about the exact size. 
    I grow rice and wheat on my farm.
    """
    
    workflow_result = server.run_complete_workflow(sample_transcript, "ramesh_001")
    print(f"Workflow Result: {json.dumps(workflow_result, indent=2)}")

if __name__ == "__main__":
    main() 