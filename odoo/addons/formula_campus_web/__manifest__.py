{
    "name": "Formula University Public Campus",
    "summary": "Published university catalogue and admissions desk for Formula University",
    "version": "18.0.1.1.0",
    "category": "Education",
    "license": "AGPL-3",
    "depends": ["web", "auth_signup", "campus_portal"],
    "data": [
        "security/ir.model.access.csv",
        "data/programs.xml",
        "data/admission_sequences.xml",
        "views/website.xml",
        "views/editor.xml",
        "views/admission.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
