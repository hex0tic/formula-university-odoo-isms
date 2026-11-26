{
    "name": "Formula Campus — Academic Plus",
    "version": "18.0.1.0.0",
    "summary": "Course registration, timetable, attendance, GPA, transcript and graduation checks",
    "category": "Education",
    "author": "Formula5 баг (ШУТИС МХТС)",
    "license": 'AGPL-3',
    "depends": ["campus_university"],
    "data": [
        "security/campus_academic_plus_security.xml",
        "security/ir.model.access.csv",
        "data/academic_policy.xml",
        "views/academic_plus_views.xml",
        "report/transcript_report.xml",
    ],
    "application": False,
    "installable": True,
}
