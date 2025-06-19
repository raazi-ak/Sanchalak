"""
Eligibility Checker Agent for Farmer AI Pipeline

Determines farmer eligibility for government schemes based on extracted information
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

from config import get_settings
from models import (
    FarmerInfo, GovernmentScheme, EligibilityCheck, EligibilityResponse, 
    EligibilityRule, EligibilityStatus
)
from utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

class EligibilityCheckerAgent:
    """Agent for checking farmer eligibility against government schemes"""
    
    def __init__(self):
        self.schemes_db = []
        self.eligibility_weights = {}
        self.is_initialized = False
        self.min_score_threshold = 0.6  # Minimum score for eligibility
        
    async def initialize(self):
        """Initialize the eligibility checker"""
        try:
            logger.info("Initializing Eligibility Checker Agent...")
            
            # Load default schemes
            await self._load_default_schemes()
            
            # Initialize weights for different criteria
            self._initialize_weights()
            
            self.is_initialized = True
            logger.info("Eligibility Checker Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Eligibility Checker Agent: {str(e)}")
            raise
    
    async def _load_default_schemes(self):
        """Load default government schemes"""
        self.schemes_db = [
            GovernmentScheme(
                scheme_id="pm_kisan",
                name="PM-KISAN",
                name_hindi="प्रधानमंत्री किसान सम्मान निधि",
                description="Income support of Rs 6000 per year to eligible farmer families",
                description_hindi="पात्र किसान परिवारों को प्रति वर्ष 6000 रुपये की आय सहायता",
                benefit_amount=6000.0,
                benefit_type="direct_transfer",
                eligibility_rules=[
                    EligibilityRule(field="land_size_acres", operator="<=", value=5.0, weight=0.9),
                    EligibilityRule(field="land_ownership", operator="==", value="owned", weight=0.8)
                ],
                target_beneficiaries=["small farmers", "marginal farmers"],
                implementing_agency="Ministry of Agriculture",
                application_process="Online application through PM-KISAN portal",
                required_documents=["Aadhaar", "Bank account", "Land records"],
                official_website="https://www.pmkisan.gov.in/",
                is_active=True
            ),
            GovernmentScheme(
                scheme_id="pmfby",
                name="PMFBY",
                name_hindi="प्रधानमंत्री फसल बीमा योजना",
                description="Crop insurance scheme providing coverage against crop loss",
                description_hindi="फसल हानि के विरुद्ध कवरेज प्रदान करने वाली फसल बीमा योजना",
                benefit_amount=None,
                benefit_type="insurance",
                eligibility_rules=[
                    EligibilityRule(field="crops", operator="in", value=["wheat", "rice", "cotton", "sugarcane"], weight=0.8)
                ],
                target_beneficiaries=["all farmers"],
                implementing_agency="Ministry of Agriculture",
                application_process="Through banks and insurance companies",
                required_documents=["Aadhaar", "Bank account", "Land records", "Sowing certificate"],
                official_website="https://pmfby.gov.in/",
                is_active=True
            ),
            GovernmentScheme(
                scheme_id="kcc",
                name="Kisan Credit Card",
                name_hindi="किसान क्रेडिट कार्ड",
                description="Credit support for agricultural and allied activities",
                description_hindi="कृषि और संबद्ध गतिविधियों के लिए ऋण सहायता",
                benefit_amount=None,
                benefit_type="credit",
                eligibility_rules=[
                    EligibilityRule(field="land_size_acres", operator=">=", value=0.5, weight=0.7),
                    EligibilityRule(field="age", operator=">=", value=18, weight=0.9),
                    EligibilityRule(field="age", operator="<=", value=75, weight=0.9)
                ],
                target_beneficiaries=["farmers", "tenant farmers", "sharecroppers"],
                implementing_agency="Banks",
                application_process="Through banks and cooperative societies",
                required_documents=["Aadhaar", "PAN", "Land records", "Income proof"],
                is_active=True
            ),
            GovernmentScheme(
                scheme_id="soil_health_card",
                name="Soil Health Card Scheme",
                name_hindi="मृदा स्वास्थ्य कार्ड योजना",
                description="Soil testing and nutrient management recommendations",
                description_hindi="मृदा परीक्षण और पोषक तत्व प्रबंधन सिफारिशें",
                benefit_amount=None,
                benefit_type="service",
                eligibility_rules=[
                    EligibilityRule(field="land_size_acres", operator=">=", value=0.1, weight=0.6)
                ],
                target_beneficiaries=["all farmers"],
                implementing_agency="Department of Agriculture",
                application_process="Through agriculture extension centers",
                required_documents=["Land records", "Aadhaar"],
                is_active=True
            ),
            GovernmentScheme(
                scheme_id="pradhan_mantri_krishi_sinchai_yojana",
                name="PM Krishi Sinchai Yojana",
                name_hindi="प्रधानमंत्री कृषि सिंचाई योजना",
                description="Irrigation support and water conservation",
                description_hindi="सिंचाई सहायता और जल संरक्षण",
                benefit_amount=None,
                benefit_type="subsidy",
                eligibility_rules=[
                    EligibilityRule(field="irrigation_type", operator="in", value=["drip", "sprinkler"], weight=0.8),
                    EligibilityRule(field="land_size_acres", operator=">=", value=1.0, weight=0.7)
                ],
                target_beneficiaries=["farmers adopting micro-irrigation"],
                implementing_agency="Ministry of Water Resources",
                application_process="Through state agriculture departments",
                required_documents=["Aadhaar", "Land records", "Water source proof"],
                is_active=True
            )
        ]
        
        logger.info(f"Loaded {len(self.schemes_db)} default schemes")
    
    def _initialize_weights(self):
        """Initialize weights for different eligibility criteria"""
        self.eligibility_weights = {
            "land_size_acres": 0.9,
            "annual_income": 0.8,
            "age": 0.7,
            "crops": 0.8,
            "irrigation_type": 0.6,
            "land_ownership": 0.7,
            "family_size": 0.5,
            "state": 0.6,
            "gender": 0.4
        }
    
    async def check_eligibility(
        self,
        farmer_info: FarmerInfo,
        explain_decisions: bool = True
    ) -> EligibilityResponse:
        """
        Check farmer eligibility for all schemes
        
        Args:
            farmer_info: Farmer information
            explain_decisions: Whether to include explanations
            
        Returns:
            EligibilityResponse with results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Checking eligibility for farmer: {farmer_info.name or 'Unknown'}")
            
            eligible_schemes = []
            ineligible_schemes = []
            recommended_actions = []
            
            # Check each scheme
            for scheme in self.schemes_db:
                if not scheme.is_active:
                    continue
                
                eligibility_check = await self._check_scheme_eligibility(
                    farmer_info, scheme, explain_decisions
                )
                
                if eligibility_check.status == EligibilityStatus.ELIGIBLE:
                    eligible_schemes.append(eligibility_check)
                elif eligibility_check.status == EligibilityStatus.PARTIALLY_ELIGIBLE:
                    eligible_schemes.append(eligibility_check)
                else:
                    ineligible_schemes.append(eligibility_check)
            
            # Sort by eligibility score
            eligible_schemes.sort(key=lambda x: x.score, reverse=True)
            ineligible_schemes.sort(key=lambda x: x.score, reverse=True)
            
            # Generate recommendations
            recommended_actions = self._generate_recommendations(
                farmer_info, eligible_schemes, ineligible_schemes
            )
            
            processing_time = time.time() - start_time
            
            response = EligibilityResponse(
                farmer_info=farmer_info,
                eligible_schemes=eligible_schemes,
                ineligible_schemes=ineligible_schemes,
                recommended_actions=recommended_actions,
                total_schemes_checked=len(self.schemes_db),
                eligible_count=len(eligible_schemes),
                processing_time=processing_time
            )
            
            logger.info(f"Eligibility check completed: {len(eligible_schemes)} eligible schemes")
            return response
            
        except Exception as e:
            logger.error(f"Eligibility check failed: {str(e)}")
            return EligibilityResponse(
                farmer_info=farmer_info,
                total_schemes_checked=0,
                eligible_count=0,
                processing_time=time.time() - start_time
            )
    
    async def _check_scheme_eligibility(
        self,
        farmer_info: FarmerInfo,
        scheme: GovernmentScheme,
        explain_decisions: bool
    ) -> EligibilityCheck:
        """Check eligibility for a single scheme"""
        
        try:
            passed_rules = []
            failed_rules = []
            missing_info = []
            total_score = 0.0
            total_weight = 0.0
            
            # Check each eligibility rule
            for rule in scheme.eligibility_rules:
                farmer_value = getattr(farmer_info, rule.field, None)
                
                if farmer_value is None:
                    missing_info.append(rule.field)
                    continue
                
                rule_passed = self._evaluate_rule(farmer_value, rule)
                
                if rule_passed:
                    passed_rules.append(rule.field)
                    total_score += rule.weight
                else:
                    failed_rules.append(rule.field)
                
                total_weight += rule.weight
            
            # Calculate final score
            if total_weight > 0:
                final_score = total_score / total_weight
            else:
                final_score = 0.0
            
            # Determine eligibility status
            status = self._determine_eligibility_status(
                final_score, missing_info, failed_rules
            )
            
            # Generate explanation
            explanation = ""
            if explain_decisions:
                explanation = self._generate_explanation(
                    scheme, status, final_score, passed_rules, failed_rules, missing_info
                )
            
            # Generate recommendations for this scheme
            recommendations = self._generate_scheme_recommendations(
                farmer_info, scheme, failed_rules, missing_info
            )
            
            return EligibilityCheck(
                scheme_id=scheme.scheme_id,
                scheme_name=scheme.name,
                status=status,
                score=final_score,
                passed_rules=passed_rules,
                failed_rules=failed_rules,
                missing_info=missing_info,
                explanation=explanation,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Failed to check eligibility for scheme {scheme.scheme_id}: {str(e)}")
            return EligibilityCheck(
                scheme_id=scheme.scheme_id,
                scheme_name=scheme.name,
                status=EligibilityStatus.INSUFFICIENT_DATA,
                score=0.0,
                explanation="Error occurred during eligibility check"
            )
    
    def _evaluate_rule(self, farmer_value: Any, rule: EligibilityRule) -> bool:
        """Evaluate a single eligibility rule"""
        try:
            if rule.operator == "==":
                return farmer_value == rule.value
            elif rule.operator == "!=":
                return farmer_value != rule.value
            elif rule.operator == ">=":
                return float(farmer_value) >= float(rule.value)
            elif rule.operator == "<=":
                return float(farmer_value) <= float(rule.value)
            elif rule.operator == ">":
                return float(farmer_value) > float(rule.value)
            elif rule.operator == "<":
                return float(farmer_value) < float(rule.value)
            elif rule.operator == "in":
                if isinstance(rule.value, list):
                    if isinstance(farmer_value, list):
                        return any(item in rule.value for item in farmer_value)
                    else:
                        return farmer_value in rule.value
                else:
                    return str(rule.value).lower() in str(farmer_value).lower()
            elif rule.operator == "not_in":
                if isinstance(rule.value, list):
                    if isinstance(farmer_value, list):
                        return not any(item in rule.value for item in farmer_value)
                    else:
                        return farmer_value not in rule.value
                else:
                    return str(rule.value).lower() not in str(farmer_value).lower()
            else:
                logger.warning(f"Unknown operator: {rule.operator}")
                return False
                
        except (ValueError, TypeError) as e:
            logger.warning(f"Rule evaluation error: {str(e)}")
            return False
    
    def _determine_eligibility_status(
        self,
        score: float,
        missing_info: List[str],
        failed_rules: List[str]
    ) -> EligibilityStatus:
        """Determine overall eligibility status"""
        
        if len(missing_info) > 2:  # Too much missing information
            return EligibilityStatus.INSUFFICIENT_DATA
        
        if score >= 0.8:
            return EligibilityStatus.ELIGIBLE
        elif score >= 0.5:
            return EligibilityStatus.PARTIALLY_ELIGIBLE
        else:
            return EligibilityStatus.NOT_ELIGIBLE
    
    def _generate_explanation(
        self,
        scheme: GovernmentScheme,
        status: EligibilityStatus,
        score: float,
        passed_rules: List[str],
        failed_rules: List[str],
        missing_info: List[str]
    ) -> str:
        """Generate human-readable explanation"""
        
        explanation_parts = []
        
        # Status explanation
        if status == EligibilityStatus.ELIGIBLE:
            explanation_parts.append(f"You are eligible for {scheme.name} with a score of {score:.1%}")
        elif status == EligibilityStatus.PARTIALLY_ELIGIBLE:
            explanation_parts.append(f"You are partially eligible for {scheme.name} with a score of {score:.1%}")
        elif status == EligibilityStatus.NOT_ELIGIBLE:
            explanation_parts.append(f"You are not eligible for {scheme.name} (score: {score:.1%})")
        else:
            explanation_parts.append(f"Insufficient information to determine eligibility for {scheme.name}")
        
        # Passed criteria
        if passed_rules:
            criteria_met = ", ".join([rule.replace("_", " ").title() for rule in passed_rules])
            explanation_parts.append(f"Criteria met: {criteria_met}")
        
        # Failed criteria
        if failed_rules:
            criteria_failed = ", ".join([rule.replace("_", " ").title() for rule in failed_rules])
            explanation_parts.append(f"Criteria not met: {criteria_failed}")
        
        # Missing information
        if missing_info:
            info_needed = ", ".join([info.replace("_", " ").title() for info in missing_info])
            explanation_parts.append(f"Additional information needed: {info_needed}")
        
        return ". ".join(explanation_parts) + "."
    
    def _generate_scheme_recommendations(
        self,
        farmer_info: FarmerInfo,
        scheme: GovernmentScheme,
        failed_rules: List[str],
        missing_info: List[str]
    ) -> List[str]:
        """Generate recommendations for a specific scheme"""
        
        recommendations = []
        
        # Recommendations based on failed rules
        for rule_field in failed_rules:
            if rule_field == "land_size_acres":
                recommendations.append("Consider consolidating land holdings or exploring schemes for your current land size")
            elif rule_field == "age":
                recommendations.append("This scheme has age restrictions. Check if family members are eligible")
            elif rule_field == "annual_income":
                recommendations.append("Income limits apply. Ensure accurate income documentation")
            elif rule_field == "crops":
                recommendations.append("Consider growing crops covered under this scheme")
            elif rule_field == "irrigation_type":
                recommendations.append("Adopt modern irrigation methods to qualify")
        
        # Recommendations for missing information
        for info_field in missing_info:
            if info_field == "land_size_acres":
                recommendations.append("Provide land size documentation")
            elif info_field == "annual_income":
                recommendations.append("Obtain income certificate from local authorities")
            elif info_field == "age":
                recommendations.append("Provide age proof (Aadhaar/Birth certificate)")
            elif info_field == "crops":
                recommendations.append("Specify which crops you grow")
        
        return recommendations
    
    def _generate_recommendations(
        self,
        farmer_info: FarmerInfo,
        eligible_schemes: List[EligibilityCheck],
        ineligible_schemes: List[EligibilityCheck]
    ) -> List[str]:
        """Generate overall recommendations for the farmer"""
        
        recommendations = []
        
        # Priority recommendations based on eligible schemes
        if eligible_schemes:
            top_scheme = eligible_schemes[0]
            recommendations.append(f"Apply for {top_scheme.scheme_name} first - highest eligibility score")
            
            if len(eligible_schemes) > 1:
                recommendations.append(f"Also consider applying for {len(eligible_schemes)-1} other eligible schemes")
        
        # Recommendations for improvement
        if farmer_info.land_size_acres and farmer_info.land_size_acres < 2:
            recommendations.append("Focus on schemes for small and marginal farmers")
        
        if not farmer_info.has_kisan_credit_card:
            recommendations.append("Consider applying for Kisan Credit Card for credit support")
        
        if farmer_info.irrigation_type == "rain fed":
            recommendations.append("Explore irrigation development schemes to increase productivity")
        
        # Documentation recommendations
        missing_docs = []
        if not farmer_info.phone_number:
            missing_docs.append("mobile number")
        if not farmer_info.bank_account:
            missing_docs.append("bank account details")
        
        if missing_docs:
            recommendations.append(f"Ensure you have: {', '.join(missing_docs)}")
        
        return recommendations
    
    async def add_scheme(self, scheme: GovernmentScheme):
        """Add a new scheme to the database"""
        try:
            self.schemes_db.append(scheme)
            logger.info(f"Added scheme: {scheme.name}")
        except Exception as e:
            logger.error(f"Failed to add scheme: {str(e)}")
    
    async def update_schemes(self, schemes: List[GovernmentScheme]):
        """Update the schemes database"""
        try:
            self.schemes_db = schemes
            logger.info(f"Updated schemes database with {len(schemes)} schemes")
        except Exception as e:
            logger.error(f"Failed to update schemes: {str(e)}")
    
    async def get_scheme_by_id(self, scheme_id: str) -> Optional[GovernmentScheme]:
        """Get a scheme by ID"""
        for scheme in self.schemes_db:
            if scheme.scheme_id == scheme_id:
                return scheme
        return None
    
    async def get_all_schemes(self) -> List[GovernmentScheme]:
        """Get all available schemes"""
        return [scheme for scheme in self.schemes_db if scheme.is_active]
    
    async def is_ready(self) -> bool:
        """Check if the agent is ready"""
        return self.is_initialized and len(self.schemes_db) > 0
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.schemes_db.clear()
            self.eligibility_weights.clear()
            self.is_initialized = False
            
            logger.info("Eligibility Checker Agent cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during Eligibility Checker cleanup: {str(e)}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get eligibility checker statistics"""
        return {
            "total_schemes": len(self.schemes_db),
            "active_schemes": len([s for s in self.schemes_db if s.is_active]),
            "scheme_categories": list(set([s.benefit_type for s in self.schemes_db])),
            "min_score_threshold": self.min_score_threshold
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Get health status of the eligibility checker"""
        try:
            stats = await self.get_stats()
            
            return {
                "status": "healthy" if self.is_initialized else "not_ready",
                "schemes_loaded": len(self.schemes_db) > 0,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }