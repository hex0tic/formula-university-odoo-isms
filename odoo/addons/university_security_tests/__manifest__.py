# -*- coding: utf-8 -*-
{
    "name": "University Security Tests",
    "version": "18.0.1.0.0",
    "summary": "Test-only security regression suite (privilege escalation, IDOR, self-approval, audit, CSRF, exports)",
    "description": """
Test-only addon. It contains no business logic and no models, views or data.
Tests run as real low-privilege users and call the ORM with ``with_user`` (no sudo),
the way an RPC client would. Each test documents the attack it simulates.
Run: MODULES=university_security_tests TAGS=/university_security_tests
""",
    "author": "Formula5 баг (ШУТИС МХТС)",
    "license": "LGPL-3",
    "category": "Hidden",
    "depends": ["university_isms", "campus_university", "university_access_review"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
