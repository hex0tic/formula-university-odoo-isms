# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
{
    "name": "Formula Campus Portal",
    "summary": "Student self-service (portal) and lecturer portal for Formula Campus records",
    "version": "18.0.1.0.0",
    "category": "Education",
    "author": "Formula5 баг (ШУТИС МХТС)",
    "license": 'AGPL-3',
    "depends": ["campus_university", "campus_academic_plus", "portal", "web"],
    "data": [
        "views/portal_templates.xml",
        "views/teacher_templates.xml",
        "views/teacher_menu.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "campus_portal/static/src/scss/portal_theme.scss",
            "campus_portal/static/src/scss/campus_portal.scss",
            "campus_portal/static/src/scss/teacher_web.scss",
        ],
        "web.assets_backend": [
            "campus_portal/static/src/scss/portal_theme.scss",
            "campus_portal/static/src/teacher/teacher_portal.scss",
            "campus_portal/static/src/teacher/teacher_portal.js",
            "campus_portal/static/src/teacher/teacher_portal.xml",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
