:- [REFERENCE_prolog_system].

% Test facts with correct arity
person('Ram Kumar Singh', 'Ram Kumar Singh').
region('Ram Kumar Singh', 'Manipur').
region_special('Ram Kumar Singh', 'manipur').
has_special_certificate('Ram Kumar Singh', true).
certificate_type('Ram Kumar Singh', 'village_authority_certificate').

% Test Manipur provision
:- write('Testing Manipur provision...'), nl.
:- apply_manipur_provision('Ram Kumar Singh'), write('✅ Manipur provision applies'), nl.
:- \+ apply_manipur_provision('Ram Kumar Singh'), write('❌ Manipur provision does not apply'), nl.

:- halt.
