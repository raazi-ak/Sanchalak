"""
Enhanced Eligibility Checker Agent with Business Rules Engine

Determines farmer eligibility for government schemes using a rule-based approach
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

# Business rules engine imports
from business_rules import BaseVariables, BaseActions, Rule
from business_rules.engine import run_all
from business_rules.variables import (
    numeric_rule_variable, string_rule_variable, 
    boolean_rule_variable, select_rule_variable
)
from business_rules.actions import rule_action
from business_rules.fields import FIELD_NUMERIC, FIELD_TEXT, FIELD_SELECT

from config import get_settings
from models import (
    FarmerInfo, GovernmentScheme, EligibilityCheck, EligibilityResponse, 
    EligibilityRule, EligibilityStatus
)
from utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class FarmerVariables(BaseVariables):
    """Variables representing farmer information for rule evaluation"""
    
    def __init__(self, farmer_info: FarmerInfo):
        self.farmer_info = farmer_info
    
    @numeric_rule_variable
    def age(self):
        """Farmer's age"""
        return self.farmer_info.age or 0
    
    @numeric_rule_variable
    def annual_income(self):
        """Farmer's annual income in rupees"""
        return self.farmer_info.annual_income or 0
    
    @numeric_rule_variable
    def land_size_acres(self):
        """Total land size in acres"""
        return self.farmer_info.land_size_acres or 0
    
    @numeric_rule_variable
    def family_size(self):
        """Number of family members"""
        return self.farmer_info.family_size or 1
    
    @string_rule_variable
    def state(self):
        """State where farmer resides"""
        return self.farmer_info.state or ""
    
    @string_rule_variable
    def district(self):
        """District where farmer resides"""
        return self.farmer_info.district or ""
    
    @string_rule_variable
    def gender(self):
        """Farmer's gender"""
        return self.farmer_info.gender or ""
    
    @string_rule_variable
    def land_ownership(self):
        """Type of land ownership"""
        return self.farmer_info.land_ownership or ""
    
    @string_rule_variable
    def irrigation_type(self):
        """Type of irrigation used"""
        return self.farmer_info.irrigation_type or ""
    
    @string_rule_variable
    def primary_crop(self):
        """Primary crop grown by farmer"""
        if self.farmer_info.crops and len(self.farmer_info.crops) > 0:
            return self.farmer_info.crops[0]
        return ""
    
    @boolean_rule_variable
    def has_bank_account(self):
        """Whether farmer has a bank account"""
        return bool(self.farmer_info.bank_account)
    
    @boolean_rule_variable
    def has_aadhaar(self):
        """Whether farmer has Aadhaar card"""
        return bool(self.farmer_info.aadhaar_number)
    
    @boolean_rule_variable
    def has_kisan_credit_card(self):
        """Whether farmer has Kisan Credit Card"""
        return self.farmer_info.has_kisan_credit_card or False
    
    @boolean_rule_variable
    def is_marginal_farmer(self):
        """Whether farmer is classified as marginal (< 2.5 acres)"""
        return (self.farmer_info.land_size_acres or 0) < 2.5
    
    @boolean_rule_variable
    def is_small_farmer(self):
        """Whether farmer is classified as small (2.5-5 acres)"""
        land_size = self.farmer_info.land_size_acres or 0
        return 2.5 <= land_size <= 5.0
    
    @boolean_rule_variable
    def grows_food_grains(self):
        """Whether farmer grows food grains"""
        if not self.farmer_info.crops:
            return False
        food_grains = ['wheat', 'rice', 'barley', 'millet', 'maize', 'pulses']
        return any(crop.lower() in food_grains for crop in self.farmer_info.crops)
    
    @boolean_rule_variable
    def grows_cash_crops(self):
        """Whether farmer grows cash crops"""
        if not self.farmer_info.crops:
            return False
        cash_crops = ['cotton', 'sugarcane', 'tobacco', 'jute']
        return any(crop.lower() in cash_crops for crop in self.farmer_info.crops)


class EligibilityActions(BaseActions):
    """Actions to be taken based on rule evaluation"""
    
    def __init__(self):
        self.results = []
        self.eligibility_scores = {}
        self.passed_rules = {}
        self.failed_rules = {}
        self.recommendations = {}
    
    @rule_action(params={"scheme_id": FIELD_TEXT, "score": FIELD_NUMERIC})
    def mark_eligible(self, scheme_id, score):
        """Mark scheme as eligible with given score"""
        self.results.append({
            "scheme_id": scheme_id,
            "eligible": True,
            "score": score,
            "action": "mark_eligible"
        })
        
        if scheme_id not in self.eligibility_scores:
            self.eligibility_scores[scheme_id] = []
        self.eligibility_scores[scheme_id].append(score)
    
    @rule_action(params={"scheme_id": FIELD_TEXT, "rule_name": FIELD_TEXT})
    def record_passed_rule(self, scheme_id, rule_name):
        """Record that a rule was passed"""
        if scheme_id not in self.passed_rules:
            self.passed_rules[scheme_id] = []
        self.passed_rules[scheme_id].append(rule_name)
    
    @rule_action(params={"scheme_id": FIELD_TEXT, "rule_name": FIELD_TEXT})
    def record_failed_rule(self, scheme_id, rule_name):
        """Record that a rule was failed"""
        if scheme_id not in self.failed_rules:
            self.failed_rules[scheme_id] = []
        self.failed_rules[scheme_id].append(rule_name)
    
    @rule_action(params={"scheme_id": FIELD_TEXT, "recommendation": FIELD_TEXT})
    def add_recommendation(self, scheme_id, recommendation):
        """Add a recommendation for the scheme"""
        if scheme_id not in self.recommendations:
            self.recommendations[scheme_id] = []
        self.recommendations[scheme_id].append(recommendation)
    
    def get_final_score(self, scheme_id):
        """Calculate final eligibility score for a scheme"""
        if scheme_id not in self.eligibility_scores:
            return 0.0
        
        scores = self.eligibility_scores[scheme_id]
        if not scores:
            return 0.0
            
        # Average of all rule scores
        return sum(scores) / len(scores)


class EnhancedEligibilityCheckerAgent:
    """Enhanced Agent for checking farmer eligibility using business rules engine"""
    
    def __init__(self):
        self.schemes_db = []
        self.business_rules = {}
        self.is_initialized = False
        self.min_score_threshold = 0.6
        
    async def initialize(self):
        """Initialize the enhanced eligibility checker"""
        try:
            logger.info("Initializing Enhanced Eligibility Checker Agent...")
            
            # Load default schemes
            await self._load_default_schemes()
            
            # Initialize business rules
            await self._initialize_business_rules()
            
            self.is_initialized = True
            logger.info("Enhanced Eligibility Checker Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced Eligibility Checker Agent: {str(e)}")
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
                    EligibilityRule(field="land_ownership", operator="==", value="owned", weight=0.8),
                    EligibilityRule(field="has_bank_account", operator="==", value=True, weight=0.7)
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
                    EligibilityRule(field="grows_food_grains", operator="==", value=True, weight=0.8),
                    EligibilityRule(field="has_bank_account", operator="==", value=True, weight=0.7),
                    EligibilityRule(field="land_size_acres", operator=">=", value=0.5, weight=0.6)
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
                    EligibilityRule(field="age", operator="<=", value=75, weight=0.9),
                    EligibilityRule(field="has_bank_account", operator="==", value=True, weight=0.8)
                ],
                target_beneficiaries=["farmers", "tenant farmers", "sharecroppers"],
                implementing_agency="Banks",
                application_process="Through banks and cooperative societies",
                required_documents=["Aadhaar", "PAN", "Land records", "Income proof"],
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
                    EligibilityRule(field="land_size_acres", operator=">=", value=1.0, weight=0.7),
                    EligibilityRule(field="has_bank_account", operator="==", value=True, weight=0.6)
                ],
                target_beneficiaries=["farmers adopting micro-irrigation"],
                implementing_agency="Ministry of Water Resources",
                application_process="Through state agriculture departments",
                required_documents=["Aadhaar", "Land records", "Water source proof"],
                is_active=True
            )
        ]
        
        logger.info(f"Loaded {len(self.schemes_db)} default schemes")
    
    async def _initialize_business_rules(self):
        """Initialize business rules for each scheme"""
        self.business_rules = {}
        
        for scheme in self.schemes_db:
            rules = []
            
            for eligibility_rule in scheme.eligibility_rules:
                rule = self._create_business_rule(scheme, eligibility_rule)
                if rule:
                    rules.append(rule)
            
            self.business_rules[scheme.scheme_id] = rules
        
        logger.info(f"Initialized business rules for {len(self.business_rules)} schemes")
    
    def _create_business_rule(self, scheme: GovernmentScheme, eligibility_rule: EligibilityRule) -> Dict:
        """Create a business rule from an eligibility rule"""
        
        try:
            # Map operators to business rules format
            operator_map = {
                "==": "equal_to",
                "!=": "not_equal_to",
                ">=": "greater_than_or_equal_to",
                "<=": "less_than_or_equal_to",
                ">": "greater_than",
                "<": "less_than",
                "in": "contains_all",
                "not_in": "does_not_contain"
            }
            
            if eligibility_rule.operator not in operator_map:
                logger.warning(f"Unsupported operator: {eligibility_rule.operator}")
                return None
            
            # Create condition
            condition = {
                "name": eligibility_rule.field,
                "operator": operator_map[eligibility_rule.operator],
                "value": eligibility_rule.value
            }
            
            # Create rule
            rule = {
                "conditions": {
                    "all": [condition]
                },
                "actions": [
                    {
                        "name": "mark_eligible",
                        "params": {
                            "scheme_id": scheme.scheme_id,
                            "score": eligibility_rule.weight
                        }
                    },
                    {
                        "name": "record_passed_rule",
                        "params": {
                            "scheme_id": scheme.scheme_id,
                            "rule_name": eligibility_rule.field
                        }
                    }
                ]
            }
            
            return rule
            
        except Exception as e:
            logger.error(f"Failed to create business rule: {str(e)}")
            return None
    
    async def check_eligibility_with_rules(
        self,
        farmer_info: FarmerInfo,
        explain_decisions: bool = True
    ) -> EligibilityResponse:
        """
        Check farmer eligibility using business rules engine
        
        Args:
            farmer_info: Farmer information
            explain_decisions: Whether to include explanations
            
        Returns:
            EligibilityResponse with results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Checking eligibility with rules for farmer: {farmer_info.name or 'Unknown'}")
            
            # Initialize variables and actions
            variables = FarmerVariables(farmer_info)
            actions = EligibilityActions()
            
            eligible_schemes = []
            ineligible_schemes = []
            
            # Check each scheme using business rules
            for scheme in self.schemes_db:
                if not scheme.is_active:
                    continue
                
                scheme_rules = self.business_rules.get(scheme.scheme_id, [])
                
                if scheme_rules:
                    # Run business rules for this scheme
                    try:
                        run_all(scheme_rules, variables, actions)
                    except Exception as e:
                        logger.error(f"Error running rules for scheme {scheme.scheme_id}: {str(e)}")
                        continue
                
                # Calculate final score and create eligibility check
                final_score = actions.get_final_score(scheme.scheme_id)
                passed_rules = actions.passed_rules.get(scheme.scheme_id, [])
                failed_rules = self._get_failed_rules(scheme, passed_rules)
                
                # Determine status
                status = self._determine_eligibility_status(final_score, [], failed_rules)
                
                # Generate explanation
                explanation = ""
                if explain_decisions:
                    explanation = self._generate_explanation(
                        scheme, status, final_score, passed_rules, failed_rules, []
                    )
                
                # Get recommendations
                recommendations = actions.recommendations.get(scheme.scheme_id, [])
                if not recommendations:
                    recommendations = self._generate_scheme_recommendations(
                        farmer_info, scheme, failed_rules, []
                    )
                
                eligibility_check = EligibilityCheck(
                    scheme_id=scheme.scheme_id,
                    scheme_name=scheme.name,
                    status=status,
                    score=final_score,
                    passed_rules=passed_rules,
                    failed_rules=failed_rules,
                    missing_info=[],
                    explanation=explanation,
                    recommendations=recommendations
                )
                
                if status in [EligibilityStatus.ELIGIBLE, EligibilityStatus.PARTIALLY_ELIGIBLE]:
                    eligible_schemes.append(eligibility_check)
                else:
                    ineligible_schemes.append(eligibility_check)
            
            # Sort by score
            eligible_schemes.sort(key=lambda x: x.score, reverse=True)
            ineligible_schemes.sort(key=lambda x: x.score, reverse=True)
            
            # Generate overall recommendations
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
            
            logger.info(f"Rules-based eligibility check completed: {len(eligible_schemes)} eligible schemes")
            return response
            
        except Exception as e:
            logger.error(f"Rules-based eligibility check failed: {str(e)}")
            return EligibilityResponse(
                farmer_info=farmer_info,
                total_schemes_checked=0,
                eligible_count=0,
                processing_time=time.time() - start_time
            )
    
    def _get_failed_rules(self, scheme: GovernmentScheme, passed_rules: List[str]) -> List[str]:
        """Get list of failed rules by comparing against all scheme rules"""
        all_rule_fields = [rule.field for rule in scheme.eligibility_rules]
        return [field for field in all_rule_fields if field not in passed_rules]
    
    def _determine_eligibility_status(
        self,
        score: float,
        missing_info: List[str],
        failed_rules: List[str]
    ) -> EligibilityStatus:
        """Determine overall eligibility status"""
        
        if len(missing_info) > 2:
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
            elif rule_field == "has_bank_account":
                recommendations.append("Open a bank account to be eligible for direct benefit transfers")
            elif rule_field == "has_aadhaar":
                recommendations.append("Obtain Aadhaar card for identity verification")
            elif rule_field == "grows_food_grains":
                recommendations.append("Consider growing food grains to qualify for crop insurance")
            elif rule_field == "irrigation_type":
                recommendations.append("Adopt modern irrigation methods like drip or sprinkler irrigation")
        
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
            recommendations.append(f"Apply for {top_scheme.scheme_name} first - highest eligibility score ({top_scheme.score:.1%})")
            
            if len(eligible_schemes) > 1:
                recommendations.append(f"Also consider applying for {len(eligible_schemes)-1} other eligible schemes")
        
        # Specific recommendations based on farmer profile
        if farmer_info.land_size_acres and farmer_info.land_size_acres < 2:
            recommendations.append("Focus on schemes for small and marginal farmers like PM-KISAN")
        
        if not farmer_info.has_kisan_credit_card:
            recommendations.append("Consider applying for Kisan Credit Card for credit support")
        
        if farmer_info.irrigation_type == "rain fed":
            recommendations.append("Explore irrigation development schemes to increase productivity")
        
        if not farmer_info.bank_account:
            recommendations.append("Open a bank account to receive direct benefit transfers")
        
        return recommendations
    
    # Additional methods from original class
    async def add_scheme(self, scheme: GovernmentScheme):
        """Add a new scheme and its business rules"""
        try:
            self.schemes_db.append(scheme)
            
            # Create business rules for the new scheme
            rules = []
            for eligibility_rule in scheme.eligibility_rules:
                rule = self._create_business_rule(scheme, eligibility_rule)
                if rule:
                    rules.append(rule)
            
            self.business_rules[scheme.scheme_id] = rules
            
            logger.info(f"Added scheme with rules: {scheme.name}")
        except Exception as e:
            logger.error(f"Failed to add scheme: {str(e)}")
    
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
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get eligibility checker statistics"""
        return {
            "total_schemes": len(self.schemes_db),
            "active_schemes": len([s for s in self.schemes_db if s.is_active]),
            "total_business_rules": sum(len(rules) for rules in self.business_rules.values()),
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
                "business_rules_loaded": len(self.business_rules) > 0,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            self.schemes_db.clear()
            self.business_rules.clear()
            self.is_initialized = False
            
            logger.info("Enhanced Eligibility Checker Agent cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during Enhanced Eligibility Checker cleanup: {str(e)}")


# Usage example
async def main():
    """Example usage of the enhanced eligibility checker"""
    
    # Create and initialize the enhanced agent
    agent = EnhancedEligibilityCheckerAgent()
    await agent.initialize()
    
    # Create sample farmer info
    farmer = FarmerInfo(
        name="Ram Kumar",
        age=35,
        land_size_acres=3.5,
        annual_income=50000,
        crops=["wheat", "rice"],
        irrigation_type="drip",
        land_ownership="owned",
        bank_account="yes",
        aadhaar_number="1234-5678-9012",
        has_kisan_credit_card=False,
        state="Uttar Pradesh",
        district="Agra"
    )
    
    # Check eligibility using business rules
    result = await agent.check_eligibility_with_rules(farmer, explain_decisions=True)
    
    # Print results
    print(f"Eligibility Results for {farmer.name}:")
    print(f"Eligible for {result.eligible_count} out of {result.total_schemes_checked} schemes")
    print(f"Processing time: {result.processing_time:.2f} seconds")
    
    print("\nEligible Schemes:")
    for scheme in result.eligible_schemes:
        print(f"- {scheme.scheme_name} (Score: {scheme.score:.1%})")
        print(f"  Status: {scheme.status}")
        print(f"  Explanation: {scheme.explanation}")
        print()
    
    print("Recommended Actions:")
    for action in result.recommended_actions:
        print(f"- {action}")


if __name__ == "__main__":
    asyncio.run(main())