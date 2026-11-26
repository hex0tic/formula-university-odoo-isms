# University Security Tests (test-only addon)

Regression suite for SEC-04. It has no business logic, models or views.

Run on a throwaway database only (the repository scripts create one):

    MODULES=university_security_tests TAGS=/university_security_tests odoo/scripts/run-tests.sh

Every test documents the attack it simulates. A test that FAILS reports a real finding;
its assertion must not be weakened. Findings are listed in docs/roadmap/DR_RUNBOOK.md
(section "SEC-04 findings") and in the report of the run.
