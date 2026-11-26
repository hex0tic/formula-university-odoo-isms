# -*- coding: utf-8 -*-
# Part of Formula University ERP. See LICENSE file for full copyright and licensing details.
"""Shared helpers for the campus portal service models. Not a model."""
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError

ATTENDANCE_STATUSES = ("present", "absent", "late", "excused")
ATTENDANCE_LABELS = {
    "present": "Ирсэн",
    "absent": "Таслах",
    "late": "Хоцорсон",
    "excused": "Чөлөөтэй",
}
MAX_ROWS = 300


def open_term(env):
    """The academic term that is currently open (state = open), newest first."""
    return env["campus.academic.term"].search([("state", "=", "open")], order="date_start desc", limit=1)


def selection_label(record, field_name):
    """Human label of a selection value (Mongolian labels come from the model)."""
    value = record[field_name]
    field = record._fields[field_name]
    if field.type != "selection":
        return value or ""
    return dict(field._description_selection(record.env)).get(value, value or "")


def parse_date(value):
    """Parse an ISO date string from a request. Returns None for empty or invalid input."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def in_window(today, start, end):
    """True when today lies within [start, end]. Missing bounds mean the window is closed."""
    if not start or not end:
        return False
    return start <= today <= end


def local_date(record, naive_utc):
    """Calendar date of a stored UTC datetime in the current user's timezone."""
    return fields.Datetime.context_timestamp(record, naive_utc).date()


def local_time_label(record, naive_utc):
    """HH:MM of a stored UTC datetime in the current user's timezone."""
    return fields.Datetime.context_timestamp(record, naive_utc).strftime("%H:%M")


def week_monday(day):
    return day - timedelta(days=day.weekday())


def user_error_text(error):
    """Message text of an Odoo exception, suitable for showing to the user."""
    if isinstance(error, UserError) or getattr(error, "args", None):
        return str(error.args[0]) if error.args else str(error)
    return str(error)

