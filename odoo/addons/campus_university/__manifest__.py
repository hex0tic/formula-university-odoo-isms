{
    "name": "Formula Campus — Academic Services",
    "version": "18.0.1.0.0",
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
    "application": True,
    "installable": True,
}
