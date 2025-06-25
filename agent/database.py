# database.py - Database configuration and connection management
from sqlalchemy import create_engine, Column, String, Text, Decimal, Boolean, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from contextlib import contextmanager
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class SchemeDB(Base):
    __tablename__ = 'schemes'
    
    id = Column(String(100), primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text)
    implementing_agency = Column(String(200))
    benefit_amount = Column(Decimal(12,2))
    benefit_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationship with eligibility rules
    eligibility_rules = relationship("EligibilityRuleDB", back_populates="scheme", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'implementing_agency': self.implementing_agency,
            'benefit_amount': float(self.benefit_amount) if self.benefit_amount else None,
            'benefit_type': self.benefit_type,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class EligibilityRuleDB(Base):
    __tablename__ = 'eligibility_rules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scheme_id = Column(String(100), ForeignKey('schemes.id'), nullable=False)
    field = Column(String(100), nullable=False)
    operator = Column(String(20), nullable=False)
    value = Column(JSON, nullable=False)
    weight = Column(Decimal(3,2), default=1.0)
    mandatory = Column(Boolean, default=False)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    # Relationship with scheme
    scheme = relationship("SchemeDB", back_populates="eligibility_rules")
    
    def to_dict(self):
        return {
            'id': self.id,
            'scheme_id': self.scheme_id,
            'field': self.field,
            'operator': self.operator,
            'value': self.value,
            'weight': float(self.weight) if self.weight else None,
            'mandatory': self.mandatory,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Database connection class
class DatabaseManager:
    def __init__(self, database_url=None):
        if database_url is None:
            database_url = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/welfare_schemes')
        
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def create_tables(self):
        """Create all tables in the database"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

# data_pipeline.py - Enhanced data pipeline with PostgreSQL integration
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

class EnhancedDataPipeline:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
    def load_schemes_from_json(self, json_file_path: str) -> int:
        """Load schemes data from JSON file into PostgreSQL"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                schemes_data = json.load(f)
            
            loaded_count = 0
            with self.db_manager.get_session() as session:
                for scheme_data in schemes_data:
                    # Check if scheme already exists
                    existing_scheme = session.query(SchemeDB).filter(
                        SchemeDB.id == scheme_data['id']
                    ).first()
                    
                    if existing_scheme:
                        # Update existing scheme
                        for key, value in scheme_data.items():
                            if key != 'eligibility_criteria':
                                setattr(existing_scheme, key, value)
                        existing_scheme.updated_at = datetime.now()
                    else:
                        # Create new scheme
                        scheme = SchemeDB(
                            id=scheme_data['id'],
                            name=scheme_data['name'],
                            description=scheme_data.get('description'),
                            implementing_agency=scheme_data.get('implementing_agency'),
                            benefit_amount=scheme_data.get('benefit_amount'),
                            benefit_type=scheme_data.get('benefit_type'),
                            is_active=scheme_data.get('is_active', True)
                        )
                        session.add(scheme)
                    
                    # Handle eligibility criteria
                    if 'eligibility_criteria' in scheme_data:
                        # Remove existing rules for this scheme
                        session.query(EligibilityRuleDB).filter(
                            EligibilityRuleDB.scheme_id == scheme_data['id']
                        ).delete()
                        
                        # Add new rules
                        for criteria in scheme_data['eligibility_criteria']:
                            rule = EligibilityRuleDB(
                                scheme_id=scheme_data['id'],
                                field=criteria['field'],
                                operator=criteria['operator'],
                                value=criteria['value'],
                                weight=criteria.get('weight', 1.0),
                                mandatory=criteria.get('mandatory', False),
                                description=criteria.get('description')
                            )
                            session.add(rule)
                    
                    loaded_count += 1
            
            logger.info(f"Successfully loaded {loaded_count} schemes into database")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Error loading schemes from JSON: {e}")
            raise
    
    def get_all_schemes(self, active_only: bool = True) -> List[Dict]:
        """Retrieve all schemes from database"""
        with self.db_manager.get_session() as session:
            query = session.query(SchemeDB)
            if active_only:
                query = query.filter(SchemeDB.is_active == True)
            
            schemes = query.all()
            return [scheme.to_dict() for scheme in schemes]
    
    def get_scheme_by_id(self, scheme_id: str) -> Optional[Dict]:
        """Get a specific scheme by ID with its eligibility rules"""
        with self.db_manager.get_session() as session:
            scheme = session.query(SchemeDB).filter(SchemeDB.id == scheme_id).first()
            if not scheme:
                return None
            
            scheme_dict = scheme.to_dict()
            scheme_dict['eligibility_rules'] = [rule.to_dict() for rule in scheme.eligibility_rules]
            return scheme_dict
    
    def search_schemes(self, query: str, limit: int = 10) -> List[Dict]:
        """Search schemes by name or description"""
        with self.db_manager.get_session() as session:
            schemes = session.query(SchemeDB).filter(
                and_(
                    SchemeDB.is_active == True,
                    or_(
                        SchemeDB.name.ilike(f'%{query}%'),
                        SchemeDB.description.ilike(f'%{query}%')
                    )
                )
            ).limit(limit).all()
            
            return [scheme.to_dict() for scheme in schemes]
    
    def get_schemes_by_agency(self, agency: str) -> List[Dict]:
        """Get all schemes by implementing agency"""
        with self.db_manager.get_session() as session:
            schemes = session.query(SchemeDB).filter(
                and_(
                    SchemeDB.is_active == True,
                    SchemeDB.implementing_agency.ilike(f'%{agency}%')
                )
            ).all()
            
            return [scheme.to_dict() for scheme in schemes]
    
    def update_scheme_status(self, scheme_id: str, is_active: bool) -> bool:
        """Update scheme active status"""
        try:
            with self.db_manager.get_session() as session:
                scheme = session.query(SchemeDB).filter(SchemeDB.id == scheme_id).first()
                if scheme:
                    scheme.is_active = is_active
                    scheme.updated_at = datetime.now()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error updating scheme status: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.db_manager.get_session() as session:
            total_schemes = session.query(SchemeDB).count()
            active_schemes = session.query(SchemeDB).filter(SchemeDB.is_active == True).count()
            total_rules = session.query(EligibilityRuleDB).count()
            
            # Get schemes by agency
            agencies = session.query(SchemeDB.implementing_agency).distinct().all()
            agency_count = len([a[0] for a in agencies if a[0]])
            
            return {
                'total_schemes': total_schemes,
                'active_schemes': active_schemes,
                'inactive_schemes': total_schemes - active_schemes,
                'total_eligibility_rules': total_rules,
                'unique_agencies': agency_count,
                'average_rules_per_scheme': round(total_rules / total_schemes, 2) if total_schemes > 0 else 0
            }

# eligibility_engine.py - Enhanced eligibility checking with database integration
class DatabaseEligibilityEngine:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
    def check_eligibility(self, applicant_data: Dict[str, Any], scheme_id: str = None) -> Dict[str, Any]:
        """Check eligibility for one or all schemes"""
        if scheme_id:
            return self._check_single_scheme(applicant_data, scheme_id)
        else:
            return self._check_all_schemes(applicant_data)
    
    def _check_single_scheme(self, applicant_data: Dict[str, Any], scheme_id: str) -> Dict[str, Any]:
        """Check eligibility for a single scheme"""
        with self.db_manager.get_session() as session:
            scheme = session.query(SchemeDB).filter(
                and_(SchemeDB.id == scheme_id, SchemeDB.is_active == True)
            ).first()
            
            if not scheme:
                return {'eligible': False, 'reason': 'Scheme not found or inactive'}
            
            rules = session.query(EligibilityRuleDB).filter(
                EligibilityRuleDB.scheme_id == scheme_id
            ).all()
            
            return self._evaluate_rules(applicant_data, scheme, rules)
    
    def _check_all_schemes(self, applicant_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check eligibility for all active schemes"""
        results = []
        
        with self.db_manager.get_session() as session:
            schemes = session.query(SchemeDB).filter(SchemeDB.is_active == True).all()
            
            for scheme in schemes:
                rules = session.query(EligibilityRuleDB).filter(
                    EligibilityRuleDB.scheme_id == scheme.id
                ).all()
                
                result = self._evaluate_rules(applicant_data, scheme, rules)
                result['scheme_info'] = {
                    'id': scheme.id,
                    'name': scheme.name,
                    'benefit_amount': float(scheme.benefit_amount) if scheme.benefit_amount else None,
                    'benefit_type': scheme.benefit_type,
                    'implementing_agency': scheme.implementing_agency
                }
                results.append(result)
        
        # Sort by eligibility score (descending)
        results.sort(key=lambda x: x.get('eligibility_score', 0), reverse=True)
        return results
    
    def _evaluate_rules(self, applicant_data: Dict[str, Any], scheme: SchemeDB, rules: List[EligibilityRuleDB]) -> Dict[str, Any]:
        """Evaluate eligibility rules for a scheme"""
        if not rules:
            return {
                'eligible': True,
                'eligibility_score': 1.0,
                'reason': 'No eligibility criteria defined',
                'matched_criteria': [],
                'failed_criteria': []
            }
        
        total_weight = 0
        achieved_weight = 0
        matched_criteria = []
        failed_criteria = []
        mandatory_failed = False
        
        for rule in rules:
            total_weight += float(rule.weight)
            field_value = applicant_data.get(rule.field)
            
            if self._evaluate_rule(field_value, rule.operator, rule.value):
                achieved_weight += float(rule.weight)
                matched_criteria.append({
                    'field': rule.field,
                    'operator': rule.operator,
                    'expected': rule.value,
                    'actual': field_value,
                    'weight': float(rule.weight)
                })
            else:
                failed_criteria.append({
                    'field': rule.field,
                    'operator': rule.operator,
                    'expected': rule.value,
                    'actual': field_value,
                    'weight': float(rule.weight),
                    'mandatory': rule.mandatory
                })
                
                if rule.mandatory:
                    mandatory_failed = True
        
        eligibility_score = achieved_weight / total_weight if total_weight > 0 else 0
        eligible = not mandatory_failed and eligibility_score >= 0.5  # 50% threshold
        
        return {
            'eligible': eligible,
            'eligibility_score': round(eligibility_score, 3),
            'reason': self._get_eligibility_reason(eligible, mandatory_failed, eligibility_score),
            'matched_criteria': matched_criteria,
            'failed_criteria': failed_criteria,
            'total_criteria': len(rules),
            'matched_count': len(matched_criteria),
            'failed_count': len(failed_criteria)
        }
    
    def _evaluate_rule(self, field_value: Any, operator: str, expected_value: Any) -> bool:
        """Evaluate a single eligibility rule"""
        if field_value is None:
            return False
        
        try:
            if operator == 'eq':
                return field_value == expected_value
            elif operator == 'ne':
                return field_value != expected_value
            elif operator == 'gt':
                return field_value > expected_value
            elif operator == 'gte':
                return field_value >= expected_value
            elif operator == 'lt':
                return field_value < expected_value
            elif operator == 'lte':
                return field_value <= expected_value
            elif operator == 'in':
                return field_value in expected_value
            elif operator == 'not_in':
                return field_value not in expected_value
            elif operator == 'contains':
                return str(expected_value).lower() in str(field_value).lower()
            elif operator == 'starts_with':
                return str(field_value).lower().startswith(str(expected_value).lower())
            elif operator == 'ends_with':
                return str(field_value).lower().endswith(str(expected_value).lower())
            else:
                return False
        except Exception as e:
            logger.error(f"Error evaluating rule: {e}")
            return False
    
    def _get_eligibility_reason(self, eligible: bool, mandatory_failed: bool, score: float) -> str:
        """Get human-readable eligibility reason"""
        if mandatory_failed:
            return "Failed mandatory eligibility criteria"
        elif not eligible:
            return f"Eligibility score too low ({score:.1%}). Minimum 50% required."
        else:
            return f"Eligible with {score:.1%} match"

# Usage example and testing
if __name__ == "__main__":
    # Initialize database
    db_manager = DatabaseManager()
    db_manager.create_tables()
    
    # Initialize pipeline
    pipeline = EnhancedDataPipeline(db_manager)
    
    # Example: Load sample data
    sample_schemes = [
        {
            "id": "PM_KISAN_001",
            "name": "PM-KISAN Samman Nidhi",
            "description": "Income support to small and marginal farmers",
            "implementing_agency": "Ministry of Agriculture & Farmers Welfare",
            "benefit_amount": 6000.00,
            "benefit_type": "Direct Cash Transfer",
            "is_active": True,
            "eligibility_criteria": [
                {
                    "field": "land_holding",
                    "operator": "lte",
                    "value": 2.0,
                    "weight": 1.0,
                    "mandatory": True,
                    "description": "Land holding should be 2 hectares or less"
                },
                {
                    "field": "occupation",
                    "operator": "eq",
                    "value": "farmer",
                    "weight": 1.0,
                    "mandatory": True,
                    "description": "Must be a farmer"
                }
            ]
        }
    ]
    
    # Save sample data to JSON and load
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_schemes, f)
        temp_file = f.name
    
    try:
        count = pipeline.load_schemes_from_json(temp_file)
        print(f"Loaded {count} schemes")
        
        # Test eligibility checking
        eligibility_engine = DatabaseEligibilityEngine(db_manager)
        
        test_applicant = {
            "land_holding": 1.5,
            "occupation": "farmer",
            "age": 45,
            "income": 50000
        }
        
        result = eligibility_engine.check_eligibility(test_applicant, "PM_KISAN_001")
        print(f"Eligibility result: {result}")
        
        # Get database stats
        stats = pipeline.get_database_stats()
        print(f"Database stats: {stats}")
        
    finally:
        import os
        os.unlink(temp_file)