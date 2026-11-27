{
    "name": "Formula Campus — Academic Services",
    "version": "18.0.1.1.0",
    "summary": "University records and independent approval of grade corrections",
    "category": "Education",
    "author": "Formula 5",
    "license": "AGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/campus_security.xml",
        "security/ir.model.access.csv",
        "data/sequences.xml",
        "views/campus_views.xml",
    ],
    "demo": ["demo/campus_demo.xml"],
    "post_init_hook": "post_init_hook",
    "application": True,
    "installable": True,
}
