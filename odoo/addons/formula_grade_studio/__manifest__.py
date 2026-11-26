# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
{
    "name": "Formula Grade Change Approval Studio",
    "summary": "Grade change queue, before/after review, stale-revision guard and approve/reject workflow UI",
    "version": "18.0.1.0.0",
    "category": "Education",
    "author": "Formula5 баг (ШУТИС МХТС)",
    "license": 'AGPL-3',
    "depends": ["campus_isms_bridge"],
    "data": [
        "views/grade_studio_menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "formula_grade_studio/static/src/grade_studio/grade_studio.scss",
            "formula_grade_studio/static/src/grade_studio/decision_dialog.js",
            "formula_grade_studio/static/src/grade_studio/grade_studio.js",
            "formula_grade_studio/static/src/grade_studio/grade_studio.xml",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
