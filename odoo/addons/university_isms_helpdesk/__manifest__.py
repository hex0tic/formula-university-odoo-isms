{
    "name": "University ISMS — Community Helpdesk",
    "version": "18.0.1.0.0",
    "summary": "Synchronize real OCA Helpdesk tickets with controlled ISMS incident decisions",
    "author": "Formula 5",
    "license": "AGPL-3",
    "depends": ["university_isms", "helpdesk_mgmt"],
    "data": [
        "security/helpdesk_security.xml", "security/ir.model.access.csv",
        "data/helpdesk_stages.xml", "views/incident_helpdesk_views.xml",
    ],
    "installable": True,
}
