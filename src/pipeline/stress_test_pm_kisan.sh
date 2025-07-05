#!/bin/bash

FARMER_ID=123456789012
API_URL="http://localhost:8001/farmer/$FARMER_ID"
CHECKER="python pm_kisan_checker.py $FARMER_ID"

function run_test() {
  echo -e "\n==============================="
  echo -e "$1"
  echo -e "==============================="
  eval "$2"
  sleep 1
  $CHECKER | grep -A 20 "FINAL REASONING SUMMARY" || $CHECKER
  echo -e "\n---------------------------------\n"
  sleep 1
}

# 1. Baseline: All eligible
run_test "1. Baseline: All eligible" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_nri\": false, \"is_government_employee\": false, \"is_pensioner\": false, \"is_professional\": false, \"is_constitutional_post_holder\": false, \"is_political_office_holder\": false, \"is_income_tax_payer\": false, \"land_ownership\": \"owned\", \"land_owner\": true, \"aadhaar_linked\": true, \"bank_account\": true, \"special_provisions\": {}, \"family_members\": [{\"relation\": \"self\", \"name\": \"Ram Kumar Singh\", \"age\": 45, \"gender\": \"male\"}, {\"relation\": \"wife\", \"name\": \"Sita Devi\", \"age\": 42, \"gender\": \"female\"}, {\"relation\": \"child\", \"name\": \"Lakshmi\", \"age\": 12, \"gender\": \"female\"}, {\"relation\": \"child\", \"name\": \"Krishna\", \"age\": 8, \"gender\": \"male\"}]}' > /dev/null"

# 2. NRI
run_test "2. NRI" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_nri\": true}' > /dev/null"

# 3. Government Employee (non-exempt post)
run_test "3. Government Employee (non-exempt post)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_nri\": false, \"is_government_employee\": true, \"government_post\": \"IAS Officer\"}' > /dev/null"

# 4. Government Employee (exempt post: Group D)
run_test "4. Government Employee (exempt post: Group D)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_government_employee\": true, \"government_post\": \"Group D\"}' > /dev/null"

# 5. High Pension Pensioner
run_test "5. High Pension Pensioner" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_government_employee\": false, \"is_pensioner\": true, \"monthly_pension\": 15000}' > /dev/null"

# 6. Professional
run_test "6. Professional" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_pensioner\": false, \"is_professional\": true, \"profession\": \"doctor\"}' > /dev/null"

# 7. Constitutional Post Holder
run_test "7. Constitutional Post Holder" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_constitutional_post_holder\": true}' > /dev/null"

# 8. Political Office Holder
run_test "8. Political Office Holder" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_constitutional_post_holder\": false, \"is_political_office_holder\": true}' > /dev/null"

# 9. Institutional Land Holder
run_test "9. Institutional Land Holder" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_political_office_holder\": false, \"land_ownership\": \"institutional\"}' > /dev/null"

# 10. Income Tax Payer
run_test "10. Income Tax Payer" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"land_ownership\": \"owned\", \"is_income_tax_payer\": true}' > /dev/null"

# 11. Multiple Exclusions (NRI + Professional)
run_test "11. Multiple Exclusions (NRI + Professional)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_nri\": true, \"is_professional\": true, \"profession\": \"lawyer\"}' > /dev/null"

# 12. Special Provisions (valid)
run_test "12. Special Provisions (valid)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_nri\": false, \"is_professional\": false, \"special_provisions\": {\"pm_kisan\": {\"region_special\": \"manipur\", \"has_special_certificate\": true, \"certificate_type\": \"village_authority_certificate\", \"special_provision_applies\": true}}}' > /dev/null"

# 13. Special Provisions (invalid/missing cert)
run_test "13. Special Provisions (invalid/missing cert)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"special_provisions\": {\"pm_kisan\": {\"region_special\": \"manipur\", \"has_special_certificate\": false}}}' > /dev/null"

# 14. Family Structure: Adult Child
run_test "14. Family Structure: Adult Child" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"special_provisions\": {}, \"family_members\": [{\"relation\": \"self\", \"name\": \"Ram Kumar Singh\", \"age\": 45, \"gender\": \"male\"}, {\"relation\": \"wife\", \"name\": \"Sita Devi\", \"age\": 42, \"gender\": \"female\"}, {\"relation\": \"child\", \"name\": \"Lakshmi\", \"age\": 23, \"gender\": \"female\"}]}' > /dev/null"

# 15. Family Structure: Missing Wife
run_test "15. Family Structure: Missing Wife" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"family_members\": [{\"relation\": \"self\", \"name\": \"Ram Kumar Singh\", \"age\": 45, \"gender\": \"male\"}, {\"relation\": \"child\", \"name\": \"Lakshmi\", \"age\": 12, \"gender\": \"female\"}]}' > /dev/null"

# 16. All requirements fail (no land, no aadhaar, no bank)
run_test "16. All requirements fail (no land, no aadhaar, no bank)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"land_owner\": false, \"aadhaar_linked\": false, \"bank_account\": false}' > /dev/null"

# 17. All requirements pass, but one exclusion (NRI)
run_test "17. All requirements pass, but one exclusion (NRI)" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"land_owner\": true, \"aadhaar_linked\": true, \"bank_account\": true, \"is_nri\": true}' > /dev/null"

# 18. All requirements and special provisions, no exclusions
run_test "18. All requirements and special provisions, no exclusions" \
  "curl -s -X PATCH $API_URL -H 'Content-Type: application/json' -d '{\"is_nri\": false, \"is_professional\": false, \"special_provisions\": {\"pm_kisan\": {\"region_special\": \"manipur\", \"has_special_certificate\": true, \"certificate_type\": \"village_authority_certificate\", \"special_provision_applies\": true}}, \"land_owner\": true, \"aadhaar_linked\": true, \"bank_account\": true, \"family_members\": [{\"relation\": \"self\", \"name\": \"Ram Kumar Singh\", \"age\": 45, \"gender\": \"male\"}, {\"relation\": \"wife\", \"name\": \"Sita Devi\", \"age\": 42, \"gender\": \"female\"}, {\"relation\": \"child\", \"name\": \"Lakshmi\", \"age\": 12, \"gender\": \"female\"}, {\"relation\": \"child\", \"name\": \"Krishna\", \"age\": 8, \"gender\": \"male\"}]}' > /dev/null" 