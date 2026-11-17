# Formula Campus — Academic Services

Odoo 18 Community module for fictional university academic records and controlled
grade correction. All sample names, email addresses and records are synthetic.

The module provides programs, courses, students, semester offerings, enrollments
and grade correction requests. Students read their own records. Lecturers read
their assigned class. Registrars maintain academic records. An academic auditor
has read-only access. ISMS roles are managed separately by `university_isms`.

A lecturer or registrar creates a draft request with a reason and evidence
reference. Submission freezes the proposed score and reason. A different registrar
approves or rejects it. Approval locks the enrollment row, checks the original
revision, and atomically updates the score and revision. Direct score writes,
forged context flags, actor changes and self-approval are rejected on the server.

Install through the project's CLI helper:

```bash
flock ../management/runtime.lock ./scripts/odoo-cli.sh \
  -i campus_university --without-demo=all \
  --test-enable --test-tags /campus_university
```

From the assignment directory, seed the standalone synthetic academic case:

```bash
python3 odoo/addons/campus_university/scripts/run_demo_seed.py
```

Passwords are generated locally and stored under `evidence/private/` with mode
0600. The seed uses stable XML IDs and preserves existing grades on repeated runs.
It does not create or overwrite real student records.

Audit and incident integration belongs in a separate `campus_isms_bridge` module.
Database administrators remain technically capable of changing database content;
application-level access controls do not provide external tamper-proof storage.
