% -*- coding: utf-8 -*-
% Prolog Eligibility System for "PM-KISAN"
% Generated on: 2025-07-04 03:48:03
% Source: "https://pmkisan.gov.in/Documents/RevisedPM-KISANOperationalGuidelines(English).pdf"
%
% This system provides eligibility checking with reasoning capabilities.
% Use the following predicates:
%   - eligible(Person) : Check if a person is eligible
%   - explain_eligibility(Person) : Get detailed explanation
%   - check_requirements(Person) : Check specific requirements
%   - show_exclusions(Person) : Show exclusion reasons

% Import required libraries for arithmetic operations

:- dynamic person/2.
:- dynamic requirement_met/2.
:- dynamic exclusion_applies/2.
:- dynamic is_constitutional_post_holder/2.
:- dynamic is_political_office_holder/2.
:- dynamic is_government_employee/2.
:- dynamic government_post/2.
:- dynamic monthly_pension/2.
:- dynamic is_income_tax_payer/2.
:- dynamic is_professional/2.
:- dynamic is_nri/2.
:- dynamic is_pensioner/2.
:- dynamic profession/2.
:- dynamic region_special/2.
:- dynamic has_special_certificate/2.
:- dynamic certificate_type/2.
:- dynamic certificate_details/2.
:- dynamic special_provisions/2.
:- dynamic family_member/3.
:- dynamic land_ownership/2.

:- discontiguous requirement/2.
:- discontiguous check_requirement/2.
:- discontiguous check_date_of_land_ownership_condition/1.
:- discontiguous exclusion_applies/2.
:- discontiguous special_provision/2.
:- discontiguous conditional_requirement/2.

% Scheme Information
scheme_name('"PM-KISAN"').
scheme_description('"Pm-Kisan is a Central Sector Scheme providing income support to all landholding farmers\' families in the country, having cultivable land."').
scheme_source('"https://pmkisan.gov.in/Documents/RevisedPM-KISANOperationalGuidelines(English).pdf"').


% Eligibility Rules

% Main eligibility rule
eligible(Person) :-
    person(Person),
    not(excluded(Person)),
    all_requirements_met(Person),
    all_conditional_requirements_met(Person),
    family_eligible(Person),
    !.

% Check if person is excluded
excluded(Person) :-
    exclusion_applies(Person, _).

% Check if all requirements are met
all_requirements_met(Person) :-
    requirement_met(Person, name),
    requirement_met(Person, age),
    requirement_met(Person, gender),
    requirement_met(Person, phone_number),
    requirement_met(Person, state),
    requirement_met(Person, district),
    requirement_met(Person, sub_district_block),
    requirement_met(Person, village),
    requirement_met(Person, land_size_acres),
    requirement_met(Person, land_owner),
    requirement_met(Person, date_of_land_ownership),
    requirement_met(Person, bank_account),
    requirement_met(Person, account_number),
    requirement_met(Person, ifsc_code),
    requirement_met(Person, aadhaar_number),
    requirement_met(Person, aadhaar_linked),
    requirement_met(Person, category).

% Check conditional requirements
all_conditional_requirements_met(Person) :-
    findall(Req, conditional_requirement(Person, Req), Reqs),
    all_conditional_requirements_met_list(Person, Reqs).

all_conditional_requirements_met_list(_, []).
all_conditional_requirements_met_list(Person, [Req|Rest]) :-
    check_conditional_requirement_logic(Person, Req),
    all_conditional_requirements_met_list(Person, Rest).

% Individual requirement checking
requirement_met(Person, Req) :-
    requirement(Person, Req),
    check_requirement(Person, Req).

% Conditional requirement checking - only check if the requirement actually applies
check_conditional_requirement(Person, Req) :-
    conditional_requirement(Person, Req),
    check_conditional_requirement_logic(Person, Req).

% Basic Required Fields

% Requirement: "Name must be provided"
requirement(Person, name) :-
    person(Person).

check_requirement(Person, name) :-
    name(Person, Value),
    check_name_condition(Value).

check_name_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null.

% Requirement: "Age must be provided and valid"
requirement(Person, age) :-
    person(Person).

check_requirement(Person, age) :-
    age(Person, Value),
    check_age_condition(Value).

check_age_condition(Value) :-
    integer(Value),
    Value >= 18,
    Value =< 120.

% Requirement: "Gender must be provided"
requirement(Person, gender) :-
    person(Person).

check_requirement(Person, gender) :-
    gender(Person, Value),
    check_gender_condition(Value).

check_gender_condition(Value) :-
    (atom(Value) -> downcase_atom(Value, V2) ; atom_string(Value, Str), downcase_atom(Str, V2)),
    member(V2, ['male', 'female', 'other']).

% Requirement: "Phone number must be provided"
requirement(Person, phone_number) :-
    person(Person).

check_requirement(Person, phone_number) :-
    phone_number(Person, Value),
    check_phone_number_condition(Value).

check_phone_number_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null,
    % Basic phone number validation (10 digits)
    atom_string(Value, Str),
    string_length(Str, 10),
    forall(sub_string(Str, _, 1, _, Char), char_type(Char, digit)).

% Requirement: "State must be provided"
requirement(Person, state) :-
    person(Person).

check_requirement(Person, state) :-
    state(Person, Value),
    check_state_condition(Value).

check_state_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null.

% Requirement: "District must be provided"
requirement(Person, district) :-
    person(Person).

check_requirement(Person, district) :-
    district(Person, Value),
    check_district_condition(Value).

check_district_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null.

% Requirement: "Sub-district block must be provided"
requirement(Person, sub_district_block) :-
    person(Person).

check_requirement(Person, sub_district_block) :-
    sub_district_block(Person, Value),
    check_sub_district_block_condition(Value).

check_sub_district_block_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null.

% Requirement: "Village must be provided"
requirement(Person, village) :-
    person(Person).

check_requirement(Person, village) :-
    village(Person, Value),
    check_village_condition(Value).

check_village_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null.

% Requirement: "Land size in acres must be provided"
requirement(Person, land_size_acres) :-
    person(Person).

check_requirement(Person, land_size_acres) :-
    land_size_acres(Person, Value),
    check_land_size_acres_condition(Value).

check_land_size_acres_condition(Value) :-
    number(Value),
    Value > 0.

% Requirement: "Account number must be provided"
requirement(Person, account_number) :-
    person(Person).

check_requirement(Person, account_number) :-
    account_number(Person, Value),
    check_account_number_condition(Value).

check_account_number_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null,
    % Basic account number validation (numeric)
    atom_string(Value, Str),
    forall(sub_string(Str, _, 1, _, Char), char_type(Char, digit)).

% Requirement: "IFSC code must be provided"
requirement(Person, ifsc_code) :-
    person(Person).

check_requirement(Person, ifsc_code) :-
    ifsc_code(Person, Value),
    check_ifsc_code_condition(Value).

check_ifsc_code_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null,
    % Basic IFSC validation (11 characters, alphanumeric)
    atom_string(Value, Str),
    string_length(Str, 11).

% Requirement: "Aadhaar number must be provided"
requirement(Person, aadhaar_number) :-
    person(Person).

check_requirement(Person, aadhaar_number) :-
    aadhaar_number(Person, Value),
    check_aadhaar_number_condition(Value).

check_aadhaar_number_condition(Value) :-
    nonvar(Value),
    Value \= '',
    Value \= null,
    % Basic Aadhaar validation (12 digits)
    atom_string(Value, Str),
    string_length(Str, 12),
    forall(sub_string(Str, _, 1, _, Char), char_type(Char, digit)).

% Existing Requirements (Updated)

% Requirement: "Must be a landholding farmer family as per land records of the State/UT"
requirement(Person, land_owner) :-
    person(Person).

check_requirement(Person, land_owner) :-
    land_owner(Person, Value),
    check_land_owner_condition(Value).

check_land_owner_condition(Value) :-
    is_true(Value).

% Requirement: "Land ownership as on 01.02.2019 is required for eligibility"
requirement(Person, date_of_land_ownership) :-
    person(Person).

check_requirement(Person, date_of_land_ownership) :-
    date_of_land_ownership(Person, Value),
    check_date_of_land_ownership_condition(Value).

check_date_of_land_ownership_condition(Value) :-
    % Convert string dates to comparable format and check if ownership date is on or before 2019-02-01
    (   atom(Value) -> atom_string(Value, DateStr) ; DateStr = Value),
    % For PM-KISAN, land ownership must be on or before 01.02.2019
    DateStr @=< "2019-02-01".

% Requirement: "Aadhaar number must be provided"
requirement(Person, aadhaar_linked) :-
    person(Person).

check_requirement(Person, aadhaar_linked) :-
    aadhaar_linked(Person, Value),
    check_aadhaar_linked_condition(Value).

check_aadhaar_linked_condition(Value) :-
    is_true(Value).

% Requirement: "Must have a valid bank account for Direct Benefit Transfer"
requirement(Person, bank_account) :-
    person(Person).

check_requirement(Person, bank_account) :-
    bank_account(Person, Value),
    check_bank_account_condition(Value).

check_bank_account_condition(Value) :-
    is_true(Value).

% Requirement: "Category information to be captured for all beneficiaries"
requirement(Person, category) :-
    person(Person).

check_requirement(Person, category) :-
    category(Person, Value),
    check_category_condition(Value).

check_category_condition(Value) :-
    (atom(Value) -> downcase_atom(Value, V2) ; atom_string(Value, Str), downcase_atom(Str, V2)),
    member(V2, ['sc', 'st', 'general', 'minority', 'bpl']).

% Conditional Requirements

% Conditional: If government employee, then government post is required
conditional_requirement(Person, government_employee_post) :-
    person(Person),
    is_government_employee(Person, true).

check_conditional_requirement_logic(Person, government_employee_post) :-
    government_post(Person, Post),
    nonvar(Post),
    Post \= '',
    Post \= null.

% Conditional: If professional, then profession is required
conditional_requirement(Person, professional_profession) :-
    person(Person),
    is_professional(Person, true).

check_conditional_requirement_logic(Person, professional_profession) :-
    profession(Person, Prof),
    nonvar(Prof),
    Prof \= '',
    Prof \= null.

% Conditional: If pensioner, then monthly pension is required
conditional_requirement(Person, pensioner_pension) :-
    person(Person),
    is_pensioner(Person, true).

check_conditional_requirement_logic(Person, pensioner_pension) :-
    monthly_pension(Person, Pension),
    number(Pension),
    Pension >= 0.

% Conditional: If special region, then special certificate is required
conditional_requirement(Person, special_region_certificate) :-
    person(Person),
    region_special(Person, Region),
    Region \= 'none',
    Region \= none,
    Region \= 'None'.

check_conditional_requirement_logic(Person, special_region_certificate) :-
    has_special_certificate(Person, HasCert),
    is_true(HasCert).

% Family Eligibility (Updated)

% Strict family eligibility - ineligible if any child is 18 or older
family_eligible(Person) :-
    family_member(Person, 'self', _),
    family_member(Person, 'wife', _),
    % Collect all children and check their ages
    findall(Age, family_member(Person, 'child', Age), ChildAges),
    % Check that all children are minors (< 18)
    forall(member(Age, ChildAges), Age < 18).

family_eligible(Person) :-
    family_member(Person, 'self', _),
    family_member(Person, 'husband', _),
    family_member(Person, 'child', MinorAge),
    MinorAge < 18,
    \+ (family_member(Person, 'child', AdultAge), AdultAge >= 18).

% Requirement: "Special provisions apply for North East, Jharkhand, Manipur, and Nagaland (see special_provisions)"
requirement(Person, region) :-
    person(Person).

check_requirement(Person, region) :-
    region(Person, Value),
    check_region_condition(Value).

check_region_condition(Value) :-
    (atom(Value) -> downcase_atom(Value, _) ; atom_string(Value, Str), downcase_atom(Str, _)).
    % Accept any region, but always case-insensitive

% Exclusion Rules

% Exclusion: All Institutional Land holders
exclusion_applies(Person, institutional_land_holder) :-
    person(Person),
    land_ownership(Person, 'institutional'),
    check_institutional_land_holder(Person).

check_institutional_land_holder(Person) :-
    land_ownership(Person, 'institutional').

% Exclusion: Families with members who are or were holders of constitutional posts
exclusion_applies(Person, constitutional_post_holder) :-
    person(Person),
    is_constitutional_post_holder(Person, true).

check_constitutional_post_holder(Person) :-
    is_constitutional_post_holder(Person, true).

% Exclusion: Former/present Ministers, MPs, MLAs, Mayors, District Panchayat Chairpersons
exclusion_applies(Person, political_office_holder) :-
    person(Person),
    is_political_office_holder(Person, true).

check_political_office_holder(Person) :-
    is_political_office_holder(Person, true).

% Exclusion: Serving/retired officers and employees of Central/State Government (except Group D/MTS)
exclusion_applies(Person, government_employee) :-
    person(Person),
    is_government_employee(Person, true),
    government_post(Person, Post),
    not(member(Post, ['Group D', 'MTS', 'Multi Tasking Staff'])).

check_government_employee(Person) :-
    is_government_employee(Person, true),
    government_post(Person, Post),
    not(member(Post, ['Group D', 'MTS', 'Multi Tasking Staff'])).

% Exclusion: Pensioners with monthly pension >= Rs.10,000 (except Group D/MTS)
exclusion_applies(Person, high_pension_pensioner) :-
    person(Person),
    is_pensioner(Person, true),
    monthly_pension(Person, Pension),
    Pension >= 10000,
    % Check if they were Group D/MTS employee (exempt from pension exclusion)
    not(was_group_d_mts_employee(Person)).

check_high_pension_pensioner(Person) :-
    is_pensioner(Person, true),
    monthly_pension(Person, Pension),
    Pension >= 10000,
    not(was_group_d_mts_employee(Person)).

% Helper predicate to check if person was a Group D/MTS employee
was_group_d_mts_employee(Person) :-
    government_post(Person, Post),
    member(Post, ['Group D', 'MTS', 'Multi Tasking Staff']).

% Exclusion: Income tax payers in last assessment year
exclusion_applies(Person, income_tax_payer) :-
    person(Person),
    is_income_tax_payer(Person, true).

check_income_tax_payer(Person) :-
    is_income_tax_payer(Person, true).

% Exclusion: Professionals (Doctors, Engineers, Lawyers, CAs, Architects) practicing and registered
exclusion_applies(Person, professional) :-
    person(Person),
    is_professional(Person, true).

check_professional(Person) :-
    is_professional(Person, true).

% Exclusion: NRIs as per Income Tax Act, 1961
exclusion_applies(Person, nri) :-
    person(Person),
    is_nri(Person, true).

check_nri(Person) :-
    is_nri(Person, true).

% Special Provisions

% Access special provisions data from EFR models
% These predicates read from the special_provisions dict structure
% Simplified version that doesn't use get_dict/3
get_pm_kisan_region_special(Person, Region) :-
    region_special(Person, Region).

get_pm_kisan_has_special_certificate(Person, HasCert) :-
    has_special_certificate(Person, HasCert).

get_pm_kisan_certificate_type(Person, CertType) :-
    certificate_type(Person, CertType).

get_pm_kisan_certificate_details(Person, CertDetails) :-
    certificate_details(Person, CertDetails).

% Updated special provision predicates that work with EFR data structure
% Special provision for "North East States"
special_provision(Person, 'north_east_states') :-
    person(Person),
    region(Person, 'North East States'),  % Regular region check
    get_pm_kisan_region_special(Person, 'north_east'),  % Special provision check
    apply_north_east_states_provision(Person).

apply_north_east_states_provision(Person) :-
    % "In North Eastern States, where land ownership rights are community-based and it may not be possible to assess the quantum of landholder farmers, an alternate implementation mechanism for eligibility will be developed and approved by a Committee of Union Ministers and State Chief Ministers or their representatives, based on proposals by the concerned North Eastern States."
    % Check if special certificate is provided
    get_pm_kisan_has_special_certificate(Person, HasCert),
    is_true(HasCert).

% Special provision for "Manipur"
special_provision(Person, 'manipur') :-
    person(Person),
    region(Person, 'Manipur'),  % Regular region check
    get_pm_kisan_region_special(Person, 'manipur'),  % Special provision check
    apply_manipur_provision(Person).

apply_manipur_provision(Person) :-
    % "For identification of bona fide beneficiaries under PM-Kisan Scheme in Manipur, a certificate issued by the Village authority (Chairman/Chief) authorizing any tribal family to cultivate a piece of land may be accepted. Such certification must be authenticated by the concerned sub-divisional officers."
    % Check if village authority certificate is provided
    get_pm_kisan_has_special_certificate(Person, HasCert),
    is_true(HasCert),
    get_pm_kisan_certificate_type(Person, CertType),
    (CertType = 'village_authority_certificate' ; CertType = 'village_chief_certificate').

% Special provision for "Nagaland"
special_provision(Person, 'nagaland') :-
    person(Person),
    region(Person, 'Nagaland'),  % Regular region check
    get_pm_kisan_region_special(Person, 'nagaland'),  % Special provision check
    apply_nagaland_provision(Person).

apply_nagaland_provision(Person) :-
    % "For community-owned cultivable land in Nagaland under permanent cultivation, a certificate issued by the village council/authority/village chieftain regarding land holding, duly verified by the administrative head of the circle/sub-division and countersigned by the Deputy Commissioner of the District, shall suffice. For Jhum land (as per Section-2(7) of the Nagaland Jhum Land Act, 1970), identification is based on certification by the village council/chief/head, verified and countersigned as above, and the beneficiary must be included in the state\'s Agriculture Census of 2015-16."
    % Check if village council certificate is provided
    get_pm_kisan_has_special_certificate(Person, HasCert),
    is_true(HasCert),
    get_pm_kisan_certificate_type(Person, CertType),
    (CertType = 'village_council_certificate' ; CertType = 'village_chief_certificate').

% Special provision for "Jharkhand"
special_provision(Person, 'jharkhand') :-
    person(Person),
    region(Person, 'Jharkhand'),  % Regular region check
    get_pm_kisan_region_special(Person, 'jharkhand'),  % Special provision check
    apply_jharkhand_provision(Person).

apply_jharkhand_provision(Person) :-
    % "In Jharkhand, the farmer must submit a \'Vanshavali (Lineage)\' linked to the entry of land record comprising their ancestor\'s name, giving a chart of successor. This lineage chart is submitted before the Gram Sabha for objections, then verified by village/circle revenue officials and countersigned by the District revenue authority. Names are uploaded to the PM-Kisan portal after verification and subject to exclusion criteria."
    % Check if Vanshavali certificate is provided
    get_pm_kisan_has_special_certificate(Person, HasCert),
    is_true(HasCert),
    get_pm_kisan_certificate_type(Person, CertType),
    CertType = 'vanshavali_certificate'.

% Updated conditional requirement for special region certificate
% Conditional: If special region, then special certificate is required
conditional_requirement(Person, special_region_certificate) :-
    person(Person),
    get_pm_kisan_region_special(Person, Region),
    Region \= 'none',
    Region \= none,
    Region \= 'None'.

check_conditional_requirement_logic(Person, special_region_certificate) :-
    get_pm_kisan_has_special_certificate(Person, HasCert),
    is_true(HasCert),
    % Additional validation based on region
    get_pm_kisan_region_special(Person, Region),
    validate_region_certificate(Person, Region).

% Validate certificate based on region
validate_region_certificate(Person, 'manipur') :-
    get_pm_kisan_certificate_type(Person, CertType),
    (CertType = 'village_authority_certificate' ; CertType = 'village_chief_certificate').

validate_region_certificate(Person, 'nagaland') :-
    get_pm_kisan_certificate_type(Person, CertType),
    (CertType = 'village_council_certificate' ; CertType = 'village_chief_certificate').

validate_region_certificate(Person, 'jharkhand') :-
    get_pm_kisan_certificate_type(Person, CertType),
    CertType = 'vanshavali_certificate'.

validate_region_certificate(Person, 'north_east') :-
    get_pm_kisan_certificate_type(Person, CertType),
    CertType = 'community_land_certificate'.

% Legacy support - if special_provisions not available, fall back to old predicates
% (These are now the main predicates, no longer legacy)

% Utility predicates

% Get field value from person data (atomic facts)
get_field_value(Person, Field, Value) :-
    call(Field, Person, Value).

% Explanation predicates
explain_eligibility(Person) :-
    write('=== Eligibility Explanation for '), write(Person), write(' ==='), nl,
    (   eligible(Person)
    ->  write('✅ ELIGIBLE'), nl,
        write('Reasons:'), nl,
        write('  ✅ All requirements met'), nl,
        (   special_provision(Person, Provision)
        ->  write('🔶 Special provision applied: '), write(Provision), nl
        ;   true
        )
    ;   write('❌ NOT ELIGIBLE'), nl,
        write('Reasons:'), nl,
        % Print exclusions
        (   exclusion_applies(Person, _)
        ->  write('  🚫 Exclusions: Found'), nl
        ;   write('  🚫 Exclusions: None'), nl
        ),
        % Print failed requirements
        (   requirement(Person, _), not(requirement_met(Person, _))
        ->  write('  ❌ Failed Requirements: Found'), nl
        ;   write('  ❌ Failed Requirements: None'), nl
        ),
        % Print failed conditional requirements
        (   conditional_requirement(Person, _), not(check_conditional_requirement(Person, _))
        ->  write('  ❌ Failed Conditional Requirements: Found'), nl
        ;   write('  ❌ Failed Conditional Requirements: None'), nl
        ),
        % Print family eligibility with more transparency
        (   not(family_eligible(Person))
        ->  (
                findall(Age, (family_member(Person, 'child', Age), Age >= 18), AdultAges),
                findall(Age, (family_member(Person, 'child', Age), Age < 18), MinorAges),
                ( AdultAges \= [] ->
                    write('  ❌ Family Structure: Ineligible due to adult children (age 18 or older): '), write(AdultAges), nl
                ; MinorAges == [] ->
                    write('  ❌ Family Structure: Ineligible - No minor children (all children are 18 or older).'), nl
                ;   write('  ❌ Family Structure: Does not meet PM-KISAN family definition'), nl,
                    write('     Required: Husband, wife, and minor children (< 18 years)'), nl
                )
            )
        ;   write('  ✅ Family Structure: Meets PM-KISAN family definition'), nl
        ),
        % Print all facts for debugging
        write('  🛠️  All facts for debugging:'), nl,
        show_person_facts(Person)
    ).

write_requirement(Req) :-
    write('  ✅ '), write(Req), nl.

write_failed_requirement(Req) :-
    write('  ❌ '), write(Req), nl.

write_exclusion(Excl) :-
    write('  🚫 '), write(Excl), nl.

% Check specific requirements (Updated to include all requirements)
check_requirements(Person) :-
    write('=== Requirements Check for '), write(Person), write(' ==='), nl,
    % Check each requirement individually
    (   requirement_met(Person, name) -> write('✅ name'), nl ; write('❌ name'), nl),
    (   requirement_met(Person, age) -> write('✅ age'), nl ; write('❌ age'), nl),
    (   requirement_met(Person, gender) -> write('✅ gender'), nl ; write('❌ gender'), nl),
    (   requirement_met(Person, phone_number) -> write('✅ phone_number'), nl ; write('❌ phone_number'), nl),
    (   requirement_met(Person, state) -> write('✅ state'), nl ; write('❌ state'), nl),
    (   requirement_met(Person, district) -> write('✅ district'), nl ; write('❌ district'), nl),
    (   requirement_met(Person, sub_district_block) -> write('✅ sub_district_block'), nl ; write('❌ sub_district_block'), nl),
    (   requirement_met(Person, village) -> write('✅ village'), nl ; write('❌ village'), nl),
    (   requirement_met(Person, land_size_acres) -> write('✅ land_size_acres'), nl ; write('❌ land_size_acres'), nl),
    (   requirement_met(Person, land_owner) -> write('✅ land_owner'), nl ; write('❌ land_owner'), nl),
    (   requirement_met(Person, date_of_land_ownership) -> write('✅ date_of_land_ownership'), nl ; write('❌ date_of_land_ownership'), nl),
    (   requirement_met(Person, bank_account) -> write('✅ bank_account'), nl ; write('❌ bank_account'), nl),
    (   requirement_met(Person, account_number) -> write('✅ account_number'), nl ; write('❌ account_number'), nl),
    (   requirement_met(Person, ifsc_code) -> write('✅ ifsc_code'), nl ; write('❌ ifsc_code'), nl),
    (   requirement_met(Person, aadhaar_number) -> write('✅ aadhaar_number'), nl ; write('❌ aadhaar_number'), nl),
    (   requirement_met(Person, aadhaar_linked) -> write('✅ aadhaar_linked'), nl ; write('❌ aadhaar_linked'), nl),
    (   requirement_met(Person, category) -> write('✅ category'), nl ; write('❌ category'), nl),
    (   requirement_met(Person, region) -> write('✅ region'), nl ; write('❌ region'), nl).

% Check conditional requirements
check_conditional_requirements(Person) :-
    write('=== Conditional Requirements Check for '), write(Person), write(' ==='), nl,
    (   check_conditional_requirement(Person, government_employee_post) -> write('✅ government_employee_post'), nl ; write('❌ government_employee_post'), nl),
    (   check_conditional_requirement(Person, professional_profession) -> write('✅ professional_profession'), nl ; write('❌ professional_profession'), nl),
    (   check_conditional_requirement(Person, pensioner_pension) -> write('✅ pensioner_pension'), nl ; write('❌ pensioner_pension'), nl),
    (   check_conditional_requirement(Person, special_region_certificate) -> write('✅ special_region_certificate'), nl ; write('❌ special_region_certificate'), nl).

check_and_report_requirement(Person, Req) :-
    (   requirement_met(Person, Req)
    ->  write('✅ '), write(Req), nl
    ;   write('❌ '), write(Req), nl
    ).

% Show exclusions
show_exclusions(Person) :-
    write('=== Exclusions Check for '), write(Person), write(' ==='), nl,
    (   excluded(Person)
    ->  findall(Excl, exclusion_applies(Person, Excl), Exclusions),
        maplist(write_exclusion, Exclusions)
    ;   write('✅ No exclusions apply'), nl
    ).

% Show all facts for a person (Updated to include all fields)
show_person_facts(Person) :-
    write('=== Facts for '), write(Person), write(' ==='), nl,
    % Show basic facts without maplist
    (   name(Person, Value) -> write('  name: '), write(Value), nl ; true),
    (   age(Person, Value) -> write('  age: '), write(Value), nl ; true),
    (   gender(Person, Value) -> write('  gender: '), write(Value), nl ; true),
    (   phone_number(Person, Value) -> write('  phone_number: '), write(Value), nl ; true),
    (   state(Person, Value) -> write('  state: '), write(Value), nl ; true),
    (   district(Person, Value) -> write('  district: '), write(Value), nl ; true),
    (   sub_district_block(Person, Value) -> write('  sub_district_block: '), write(Value), nl ; true),
    (   village(Person, Value) -> write('  village: '), write(Value), nl ; true),
    (   land_size_acres(Person, Value) -> write('  land_size_acres: '), write(Value), nl ; true),
    (   land_owner(Person, Value) -> write('  land_owner: '), write(Value), nl ; true),
    (   date_of_land_ownership(Person, Value) -> write('  date_of_land_ownership: '), write(Value), nl ; true),
    (   bank_account(Person, Value) -> write('  bank_account: '), write(Value), nl ; true),
    (   account_number(Person, Value) -> write('  account_number: '), write(Value), nl ; true),
    (   ifsc_code(Person, Value) -> write('  ifsc_code: '), write(Value), nl ; true),
    (   aadhaar_number(Person, Value) -> write('  aadhaar_number: '), write(Value), nl ; true),
    (   aadhaar_linked(Person, Value) -> write('  aadhaar_linked: '), write(Value), nl ; true),
    (   category(Person, Value) -> write('  category: '), write(Value), nl ; true),
    (   region(Person, Value) -> write('  region: '), write(Value), nl ; true).

write_family_members_list([]).
write_family_members_list([Relation-Age|Rest]) :-
    write('  • '), write(Relation), write(' (age: '), write(Age), write(')'), nl,
    write_family_members_list(Rest).

write_fact(Field-Value) :-
    write('  '), write(Field), write(': '), write(Value), nl.

% Show family structure details
show_family_structure(Person) :-
    write('=== Family Structure for '), write(Person), write(' ==='), nl,
    findall(Relation-Age, family_member(Person, Relation, Age), Members),
    (   Members \= []
    ->  write('Family Members:'), nl,
        write_family_members_list(Members),
        (   family_eligible(Person)
        ->  write('✅ Family structure meets PM-KISAN requirements'), nl
        ;   write('❌ Family structure does NOT meet PM-KISAN requirements'), nl,
            write('   Required: Husband, wife, and minor children (< 18 years)'), nl
        )
    ;   write('❌ No family members found'), nl
    ).

write_family_member(Relation-Age) :-
    write('  • '), write(Relation), write(' (age: '), write(Age), write(')'), nl.

% Comprehensive diagnostic predicate (Updated)
diagnose_eligibility(Person) :-
    write('🔍 COMPREHENSIVE ELIGIBILITY DIAGNOSIS'), nl,
    write('====================================='), nl, nl,
    
    % 1. Basic person check
    write('1️⃣ PERSON CHECK:'), nl,
    (   person(Person)
    ->  write('   ✅ Person exists in system'), nl
    ;   write('   ❌ Person not found in system'), nl
    ),
    nl,
    
    % 2. Family structure
    write('2️⃣ FAMILY STRUCTURE:'), nl,
    show_family_structure(Person),
    nl,
    
    % 3. Requirements check
    write('3️⃣ REQUIREMENTS CHECK:'), nl,
    check_requirements(Person),
    nl,
    
    % 4. Conditional requirements check
    write('4️⃣ CONDITIONAL REQUIREMENTS CHECK:'), nl,
    check_conditional_requirements(Person),
    nl,
    
    % 5. Exclusions check
    write('5️⃣ EXCLUSIONS CHECK:'), nl,
    show_exclusions(Person),
    nl,
    
    % 6. Final eligibility
    write('6️⃣ FINAL ELIGIBILITY:'), nl,
    explain_eligibility(Person),
    nl.


% Example usage and test cases

% Add a test person with a list of field-value pairs
add_test_person(Name, FieldValueList) :-
    assertz(person(Name)),
    add_person_facts(Name, FieldValueList).

add_person_facts(_, []).
add_person_facts(Name, [Field-Value | Rest]) :-
    Fact =.. [Field, Name, Value],
    assertz(Fact),
    add_person_facts(Name, Rest).

% Example: Add a farmer (template - replace with actual data)
example_farmer :-
    add_test_person('test_farmer', [
        name-'John Doe',
        age-45,
        gender-male,
        phone_number-'9876543210',
        state-'Maharashtra',
        district-'Pune',
        sub_district_block-'Haveli',
        village-'Koregaon',
        land_size_acres-5.5,
        land_owner-true,
        date_of_land_ownership-'2018-01-01',
        bank_account-true,
        account_number-'1234567890',
        ifsc_code-'SBIN0001234',
        aadhaar_number-'123456789012',
        aadhaar_linked-true,
        category-general,
        region-general
    ]),
    % Add family members for PM-KISAN eligibility
    assertz(family_member('test_farmer', 'self', 45)),
    assertz(family_member('test_farmer', 'wife', 40)),
    assertz(family_member('test_farmer', 'child', 15)).

% Example: Add an excluded person (template - replace with actual data)
example_excluded_person :-
    add_test_person('test_excluded', [
        name-'Jane Smith',
        age-35,
        gender-female,
        phone_number-'9876543211',
        state-'Delhi',
        district-'New Delhi',
        sub_district_block-'Central',
        village-'Connaught Place',
        land_size_acres-2.0,
        land_owner-false,
        date_of_land_ownership-'2020-01-01',
        bank_account-true,
        account_number-'0987654321',
        ifsc_code-'HDFC0001234',
        aadhaar_number-'987654321098',
        aadhaar_linked-true,
        category-general,
        region-general
    ]).

% Test the system
test_system :-
    write('=== Testing PM-KISAN Eligibility System ==='), nl, nl,
    write('Note: This is a template. Load actual farmer data before testing.'), nl, nl.

% --- FLEXIBLE BOOLEAN AND CASE-INSENSITIVE CHECKS ---

is_true(Value) :-
    ( Value = true ; Value = 'True' ; Value = 1 ; Value = '1' ;
      (atom(Value), downcase_atom(Value, V2), V2 = 'true') ;
      (atom(Value), downcase_atom(Value, V2), V2 = '1') ).

is_false(Value) :-
    ( Value = false ; Value = 'False' ; Value = 0 ; Value = '0' ;
      (atom(Value), downcase_atom(Value, V2), V2 = 'false') ;
      (atom(Value), downcase_atom(Value, V2), V2 = '0') ).

% --- STRING UTILITY PREDICATES ---

% Family eligibility check
family_eligible(Person) :-
    findall(Relation-Age, family_member(Person, Relation, Age), Members),
    family_eligible_check(Members).

family_eligible_check([]) :- !, fail.
family_eligible_check([Relation-Age|Rest]) :-
    (   Relation = 'child', Age < 18
    ->  family_eligible_check(Rest)
    ;   Relation = 'wife'
    ->  family_eligible_check(Rest)
    ;   family_eligible_check(Rest)
    ).

