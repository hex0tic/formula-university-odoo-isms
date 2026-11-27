{
    "name": "Formula Campus ISMS Integration",
    "version": "18.0.1.2.0",
    "summary": "Trace academic records and grade approvals in the ISMS audit log",
    "author": "Formula 5",
    "license": "AGPL-3",
    "depends": ["campus_university", "campus_portal", "university_isms"],
    "data": ["security/bridge_groups.xml", "views/grade_change_views.xml", "views/portal_incident.xml"],
    "assets": {"web.assets_backend": ["campus_isms_bridge/static/src/teacher_incident_link.xml"]},
    "installable": True,
}
