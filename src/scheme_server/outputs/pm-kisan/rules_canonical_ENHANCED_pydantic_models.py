#!/usr/bin/env python3
"""
Pydantic data classes for PM-KISAN scheme
Generated from enhanced canonical YAML
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class Relation(str, Enum):
    HUSBAND = "husband"
    WIFE = "wife"
    SON = "son"
    DAUGHTER = "daughter"
    FATHER = "father"
    MOTHER = "mother"
    BROTHER = "brother"
    SISTER = "sister"
    OTHER = "other"

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class LandOwnership(str, Enum):
    OWNED = "owned"
    LEASED = "leased"
    SHARECROPPING = "sharecropping"
    JOINT = "joint"
    UNKNOWN = "unknown"

class IrrigationType(str, Enum):
    RAIN_FED = "rain_fed"
    CANAL = "canal"
    BOREWELL = "borewell"
    WELL = "well"
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    TUBE_WELL = "tube_well"
    SURFACE = "surface"
    FLOOD = "flood"
    UNKNOWN = "unknown"

class Category(str, Enum):
    GENERAL = "general"
    SC = "sc"
    ST = "st"
    OBC = "obc"
    MINORITY = "minority"
    BPL = "bpl"

class RegionSpecial(str, Enum):
    NORTH_EAST = "north_east"
    MANIPUR = "manipur"
    NAGALAND = "nagaland"
    JHARKHAND = "jharkhand"
    NONE = "none"


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class BasicInfo:
    """Basic Info information."""
    farmer_id: str
    name: str
    age: int
    gender: Gender
    phone_number: str
    father_name: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    survey_number: Optional[str] = None
    khasra_number: Optional[str] = None

@dataclass
class Location:
    """Location information."""
    state: str
    district: str
    village: str
    sub_district_block: str
    pincode: Optional[str] = None

@dataclass
class Land:
    """Land information."""
    land_size_acres: float
    land_ownership: LandOwnership
    date_of_land_ownership: date
    irrigation_type: Optional[IrrigationType] = None

@dataclass
class Agriculture:
    """Agriculture information."""
    crops: Optional[List[str]] = None
    farming_equipment: Optional[List[str]] = None
    annual_income: Optional[float] = None

@dataclass
class FamilyMember:
    """Family member information."""
    relation: Relation
    name: str
    age: int
    gender: Gender
    occupation: Optional[str] = None
    is_minor: bool = field(init=False)

    def __post_init__(self):
        self.is_minor = self.age < 18

@dataclass
class Financial:
    """Financial information."""
    bank_account: bool
    account_number: str
    ifsc_code: str
    bank_name: Optional[str] = None
    has_kisan_credit_card: Optional[bool] = None

@dataclass
class Identity:
    """Identity information."""
    aadhaar_number: str
    aadhaar_linked: bool
    category: Category
    voter_id: Optional[str] = None

@dataclass
class Employment:
    """Employment information."""
    is_government_employee: Optional[bool] = None
    government_post: Optional[str] = None
    is_income_tax_payer: Optional[bool] = None
    is_professional: Optional[bool] = None
    profession: Optional[str] = None
    is_pensioner: Optional[bool] = None
    monthly_pension: Optional[float] = None
    is_nri: Optional[bool] = None

@dataclass
class SpecialProvisions:
    """Special Provisions information."""
    region_special: Optional[RegionSpecial] = None
    has_special_certificate: Optional[bool] = None
    certificate_type: Optional[str] = None

@dataclass
class DerivedFields:
    """Derived Fields information."""
    family_size: Optional[int] = None
    dependents: Optional[int] = None
    is_husband_wife_minor_children: Optional[bool] = None
    land_owner: Optional[bool] = None


# ============================================================================
# MAIN FARMER MODEL
# ============================================================================

@dataclass
class PMKISANFarmer:
    """Complete PM-KISAN farmer profile."""
    employment: Employment = field(default_factory=Employment)
    land: Land = field(default_factory=Land)
    financial: Financial = field(default_factory=Financial)
    special_provisions: SpecialProvisions = field(default_factory=SpecialProvisions)
    basic_info: BasicInfo = field(default_factory=BasicInfo)
    agriculture: Agriculture = field(default_factory=Agriculture)
    family_members: List[FamilyMember] = field(default_factory=list)
    derived_fields: DerivedFields = field(default_factory=DerivedFields)
    location: Location = field(default_factory=Location)
    identity: Identity = field(default_factory=Identity)

    def to_prolog_facts(self) -> List[str]:
        """Convert farmer data to Prolog facts."""
        facts = []
        person = self.basic_info.farmer_id

        # basic_info.farmer_id
        if self.basic_info.farmer_id:
            facts.append(f'farmer_id(Person, ID)')

        # basic_info.name
        if self.basic_info.name:
            facts.append(f'name(Person, Name)')

        # basic_info.age
        if self.basic_info.age:
            facts.append(f'age(Person, Age)')

        # basic_info.gender
        if self.basic_info.gender:
            facts.append(f'gender(Person, Gender)')

        # basic_info.phone_number
        if self.basic_info.phone_number:
            facts.append(f'phone_number(Person, Phone)')

        # basic_info.father_name
        if self.basic_info.father_name:
            facts.append(f'father_name(Person, FatherName)')

        # basic_info.address
        if self.basic_info.address:
            facts.append(f'address(Person, Address)')

        # basic_info.date_of_birth
        if self.basic_info.date_of_birth:
            facts.append(f'date_of_birth(Person, DateOfBirth)')

        # basic_info.survey_number
        if self.basic_info.survey_number:
            facts.append(f'survey_number(Person, SurveyNumber)')

        # basic_info.khasra_number
        if self.basic_info.khasra_number:
            facts.append(f'khasra_number(Person, KhasraNumber)')

        # location.state
        if self.location.state:
            facts.append(f'state(Person, State)')

        # location.district
        if self.location.district:
            facts.append(f'district(Person, District)')

        # location.village
        if self.location.village:
            facts.append(f'village(Person, Village)')

        # location.sub_district_block
        if self.location.sub_district_block:
            facts.append(f'sub_district_block(Person, Block)')

        # location.pincode
        if self.location.pincode:
            facts.append(f'pincode(Person, Pincode)')

        # land.land_size_acres
        facts.append(f'land_size_acres(Person, Acres)')

        # land.land_ownership
        if self.land.land_ownership:
            facts.append(f'land_ownership(Person, Type)')

        # land.date_of_land_ownership
        if self.land.date_of_land_ownership:
            facts.append(f'date_of_land_ownership(Person, Date)')

        # land.irrigation_type
        if self.land.irrigation_type:
            facts.append(f'irrigation_type(Person, Type)')

        # agriculture.crops
        if self.agriculture.crops:
            facts.append(f'crops_item(Person, Crop)')

        # agriculture.farming_equipment
        if self.agriculture.farming_equipment:
            facts.append(f'farming_equipment_item(Person, Equipment)')

        # agriculture.annual_income
        facts.append(f'annual_income(Person, Income)')

        # financial.bank_account
        facts.append(f'bank_account(Person, HasAccount)')

        # financial.bank_name
        if self.financial.bank_name:
            facts.append(f'bank_name(Person, BankName)')

        # financial.account_number
        if self.financial.account_number:
            facts.append(f'account_number(Person, AccountNumber)')

        # financial.ifsc_code
        if self.financial.ifsc_code:
            facts.append(f'ifsc_code(Person, IFSC)')

        # financial.has_kisan_credit_card
        facts.append(f'has_kisan_credit_card(Person, HasKCC)')

        # identity.aadhaar_number
        if self.identity.aadhaar_number:
            facts.append(f'aadhaar_number(Person, Aadhaar)')

        # identity.aadhaar_linked
        facts.append(f'aadhaar_linked(Person, IsLinked)')

        # identity.category
        if self.identity.category:
            facts.append(f'category(Person, Category)')

        # identity.voter_id
        if self.identity.voter_id:
            facts.append(f'voter_id(Person, VoterID)')

        # employment.is_government_employee
        facts.append(f'is_government_employee(Person, IsEmployee)')

        # employment.government_post
        if self.employment.government_post:
            facts.append(f'government_post(Person, Post)')

        # employment.is_income_tax_payer
        facts.append(f'is_income_tax_payer(Person, IsTaxPayer)')

        # employment.is_professional
        facts.append(f'is_professional(Person, IsProfessional)')

        # employment.profession
        if self.employment.profession:
            facts.append(f'profession(Person, Profession)')

        # employment.is_pensioner
        facts.append(f'is_pensioner(Person, IsPensioner)')

        # employment.monthly_pension
        facts.append(f'monthly_pension(Person, Amount)')

        # employment.is_nri
        facts.append(f'is_nri(Person, IsNRI)')

        # special_provisions.region_special
        if self.special_provisions.region_special:
            facts.append(f'region_special(Person, Region)')

        # special_provisions.has_special_certificate
        facts.append(f'has_special_certificate(Person, HasCertificate)')

        # special_provisions.certificate_type
        if self.special_provisions.certificate_type:
            facts.append(f'certificate_type(Person, Type)')

        # derived_fields.family_size
        if self.derived_fields.family_size:
            facts.append(f'family_size(Person, Size)')

        # derived_fields.dependents
        if self.derived_fields.dependents:
            facts.append(f'dependents(Person, Count)')

        # derived_fields.is_husband_wife_minor_children
        facts.append(f'is_husband_wife_minor_children(Person, IsMatch)')

        # derived_fields.land_owner
        facts.append(f'land_owner(Person, IsOwner)')

        return facts


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    """Example usage."""
    # Create a sample farmer
    farmer = PMKISANFarmer(
        basic_info=BasicInfo(
            farmer_id="FARMER001",
            name="Ram Kumar",
            age=45,
            gender=Gender.MALE,
            phone_number="9876543210"
        ),
        location=Location(
            state="Uttar Pradesh",
            district="Lucknow",
            sub_district_block="Block A",
            village="Village A"
        ),
        land=Land(
            land_size_acres=2.5,
            land_ownership=LandOwnership.OWNED,
            date_of_land_ownership=date(2018, 1, 1)
        ),
        financial=Financial(
            bank_account=True,
            account_number="1234567890",
            ifsc_code="SBIN0001234"
        ),
        identity=Identity(
            aadhaar_number="123456789012",
            aadhaar_linked=True,
            category=Category.GENERAL
        )
    )

    # Generate Prolog facts
    facts = farmer.to_prolog_facts()
    print("Generated Prolog Facts:")
    for fact in facts:
        print(fact)