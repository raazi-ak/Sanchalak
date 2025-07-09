"""
Clarification Workflow MCP Tools

Handles iterative clarification process where LLMs can:
1. Identify missing data
2. Ask for clarification
3. Update farmer data with new information
4. Repeat until all required data is collected
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import sys
import os

# Add pipeline path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from data_normalizer import DataNormalizer
from clarification_generator import ClarificationGenerator

logger = logging.getLogger(__name__)

class ClarificationWorkflow:
    """MCP tools for iterative clarification workflow."""
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1"):
        """Initialize clarification workflow tools."""
        self.data_normalizer = DataNormalizer()
        self.clarification_generator = ClarificationGenerator(lm_studio_url)
        
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of MCP tools for clarification workflow."""
        return [
            {
                "name": "start_clarification_session",
                "description": "Start a new clarification session for a farmer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_id": {
                            "type": "string",
                            "description": "Unique identifier for the farmer"
                        },
                        "current_data": {
                            "type": "object",
                            "description": "Current farmer data (can be empty for new farmers)"
                        },
                        "scheme": {
                            "type": "string",
                            "description": "Scheme name for eligibility checking",
                            "default": "pm_kisan"
                        }
                    },
                    "required": ["farmer_id"]
                }
            },
            {
                "name": "get_next_clarification_question",
                "description": "Get the next clarification question for missing data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Clarification session ID"
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority level (high/medium/low)",
                            "default": "high"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "submit_clarification_answer",
                "description": "Submit an answer to a clarification question and update farmer data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Clarification session ID"
                        },
                        "field": {
                            "type": "string",
                            "description": "Field being clarified"
                        },
                        "answer": {
                            "type": "string",
                            "description": "User's answer to the question"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence in the answer (0-1)",
                            "default": 1.0
                        }
                    },
                    "required": ["session_id", "field", "answer"]
                }
            },
            {
                "name": "check_clarification_progress",
                "description": "Check progress of clarification session",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Clarification session ID"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "finalize_clarification_session",
                "description": "Finalize clarification session and get complete farmer data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Clarification session ID"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "get_clarification_summary",
                "description": "Get summary of what clarifications are needed",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "farmer_data": {
                            "type": "object",
                            "description": "Current farmer data"
                        },
                        "scheme": {
                            "type": "string",
                            "description": "Scheme name",
                            "default": "pm_kisan"
                        }
                    },
                    "required": ["farmer_data"]
                }
            }
        ]
    
    def __init__(self, lm_studio_url: str = "http://localhost:1234/v1"):
        """Initialize clarification workflow."""
        self.data_normalizer = DataNormalizer()
        self.clarification_generator = ClarificationGenerator(lm_studio_url)
        self.active_sessions = {}  # Store active clarification sessions
    
    def start_clarification_session(self, farmer_id: str, current_data: Dict[str, Any] = None, scheme: str = "pm_kisan") -> Dict[str, Any]:
        """Start a new clarification session for a farmer."""
        try:
            session_id = f"clarification_{farmer_id}_{int(datetime.utcnow().timestamp())}"
            
            # Initialize session data
            session_data = {
                "session_id": session_id,
                "farmer_id": farmer_id,
                "scheme": scheme,
                "current_data": current_data or {},
                "missing_fields": [],
                "asked_questions": [],
                "answers": {},
                "started_at": datetime.utcnow().isoformat(),
                "status": "active"
            }
            
            # Identify missing fields
            missing_fields = self.clarification_generator.identify_missing_data(
                current_data or {}, 
                self.data_normalizer.general_required_fields
            )
            session_data["missing_fields"] = missing_fields
            
            # Store session
            self.active_sessions[session_id] = session_data
            
            return {
                "success": True,
                "session_id": session_id,
                "farmer_id": farmer_id,
                "missing_fields": missing_fields,
                "missing_count": len(missing_fields),
                "message": f"Started clarification session for farmer {farmer_id} with {len(missing_fields)} missing fields"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to start clarification session"
            }
    
    def get_next_clarification_question(self, session_id: str, priority: str = "high") -> Dict[str, Any]:
        """Get the next clarification question for missing data."""
        try:
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found"
                }
            
            session = self.active_sessions[session_id]
            
            # Get current missing fields
            missing_fields = session["missing_fields"]
            
            if not missing_fields:
                return {
                    "success": True,
                    "question": None,
                    "message": "No more questions needed - all required data collected",
                    "session_complete": True
                }
            
            # Generate questions for missing fields
            farmer_name = session["current_data"].get("name", "sir/madam")
            questions = self.clarification_generator.generate_clarification_questions(
                missing_fields, farmer_name
            )
            
            # Filter by priority
            priority_questions = [q for q in questions if q.get("priority", "medium") == priority]
            if not priority_questions:
                priority_questions = questions  # Fallback to all questions
            
            if not priority_questions:
                return {
                    "success": True,
                    "question": None,
                    "message": "No questions available for the specified priority",
                    "session_complete": False
                }
            
            # Get the first question that hasn't been asked
            asked_fields = [q["field"] for q in session["asked_questions"]]
            next_question = None
            
            for question in priority_questions:
                if question["field"] not in asked_fields:
                    next_question = question
                    break
            
            if not next_question:
                # All questions asked, check if we have answers
                return {
                    "success": True,
                    "question": None,
                    "message": "All questions have been asked",
                    "session_complete": len(session["answers"]) >= len(missing_fields)
                }
            
            # Mark question as asked
            session["asked_questions"].append(next_question)
            
            return {
                "success": True,
                "question": next_question,
                "session_id": session_id,
                "remaining_fields": len(missing_fields) - len(session["answers"]),
                "message": f"Next question for field: {next_question['field']}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get next clarification question"
            }
    
    def submit_clarification_answer(self, session_id: str, field: str, answer: str, confidence: float = 1.0) -> Dict[str, Any]:
        """Submit an answer to a clarification question and update farmer data."""
        try:
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found"
                }
            
            session = self.active_sessions[session_id]
            
            # Store the answer
            session["answers"][field] = {
                "value": answer,
                "confidence": confidence,
                "answered_at": datetime.utcnow().isoformat()
            }
            
            # Update current data
            session["current_data"][field] = answer
            
            # Remove from missing fields if present
            if field in session["missing_fields"]:
                session["missing_fields"].remove(field)
            
            return {
                "success": True,
                "session_id": session_id,
                "field": field,
                "answer": answer,
                "remaining_fields": len(session["missing_fields"]),
                "message": f"Updated {field} with answer: {answer}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to submit clarification answer"
            }
    
    def check_clarification_progress(self, session_id: str) -> Dict[str, Any]:
        """Check progress of clarification session."""
        try:
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found"
                }
            
            session = self.active_sessions[session_id]
            
            total_fields = len(session["missing_fields"]) + len(session["answers"])
            completed_fields = len(session["answers"])
            progress_percentage = (completed_fields / total_fields * 100) if total_fields > 0 else 100
            
            return {
                "success": True,
                "session_id": session_id,
                "farmer_id": session["farmer_id"],
                "progress": {
                    "completed": completed_fields,
                    "total": total_fields,
                    "percentage": progress_percentage,
                    "remaining": len(session["missing_fields"])
                },
                "missing_fields": session["missing_fields"],
                "completed_fields": list(session["answers"].keys()),
                "status": session["status"],
                "message": f"Progress: {completed_fields}/{total_fields} fields completed ({progress_percentage:.1f}%)"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to check clarification progress"
            }
    
    def finalize_clarification_session(self, session_id: str) -> Dict[str, Any]:
        """Finalize clarification session and get complete farmer data."""
        try:
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found"
                }
            
            session = self.active_sessions[session_id]
            
            # Check if all required fields are collected
            missing_fields = session["missing_fields"]
            if missing_fields:
                return {
                    "success": False,
                    "missing_fields": missing_fields,
                    "message": f"Cannot finalize - {len(missing_fields)} fields still missing"
                }
            
            # Normalize the complete data
            complete_data = session["current_data"]
            normalized_data = self.data_normalizer.normalize_farmer_data(complete_data)
            
            # Mark session as completed
            session["status"] = "completed"
            session["completed_at"] = datetime.utcnow().isoformat()
            session["final_data"] = normalized_data
            
            return {
                "success": True,
                "session_id": session_id,
                "farmer_id": session["farmer_id"],
                "complete_data": complete_data,
                "normalized_data": normalized_data,
                "session_duration": "calculated",  # Could calculate actual duration
                "message": f"Clarification session completed for farmer {session['farmer_id']}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to finalize clarification session"
            }
    
    def get_clarification_summary(self, farmer_data: Dict[str, Any], scheme: str = "pm_kisan") -> Dict[str, Any]:
        """Get summary of what clarifications are needed."""
        try:
            summary = self.clarification_generator.generate_clarification_summary(
                farmer_data, farmer_data
            )
            
            return {
                "success": True,
                "summary": summary,
                "message": f"Generated clarification summary for {summary.get('missing_count', 0)} missing fields"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get clarification summary"
            } 