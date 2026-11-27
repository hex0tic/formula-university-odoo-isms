{
    "name": "Form — Formula University Assistant",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "summary": "Personal daily briefing and chat",
    "license": "AGPL-3",
    "depends": ["campus_portal", "project"],
    "data": ["views/portal.xml"],
    "assets": {
        "formula_assistant._widget": [
            "formula_assistant/static/src/widget.js",
            "formula_assistant/static/src/widget.xml",
            "formula_assistant/static/src/widget.scss",
        ],
        "web.assets_backend": [
            ("include", "formula_assistant._widget"),
            "formula_assistant/static/src/backend.js",
        ],
        "web.assets_frontend": [
            ("include", "formula_assistant._widget"),
            "formula_assistant/static/src/frontend.js",
        ],
    },
    "installable": True,
}
