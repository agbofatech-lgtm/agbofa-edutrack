"""Server-authored field metadata for accessible, data-driven configuration forms.

The catalogue defines technical data types and dependencies, not school policy
values. No academic calendar, class list, subject list, permission assignment or
financial rule is pre-populated.
"""

from typing import Any

from institutional.permissions import (
    CONFIGURATION_APPROVE,
    CONFIGURATION_MANAGE,
    CONFIGURATION_READ,
    CONFIGURATION_SUBMIT,
    ENROLMENT_MANAGE,
    ENROLMENT_READ,
    STAFF_MANAGE,
    STAFF_READ,
)


def _field(
    name: str,
    label: str,
    field_type: str,
    *,
    required: bool = True,
    options_resource: str = "",
    choices: tuple[tuple[str, str], ...] = (),
    help_text: str = "",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "label": label,
        "type": field_type,
        "required": required,
    }
    if options_resource:
        result["options_resource"] = options_resource
    if choices:
        result["choices"] = [
            {"value": value, "label": label} for value, label in choices
        ]
    if help_text:
        result["help_text"] = help_text
    return result


CONFIGURATION_SCHEMA: tuple[dict[str, Any], ...] = (
    {
        "key": "settings",
        "label": "Institutional settings",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field("key", "Setting key", "text", help_text="Stable lowercase key."),
            _field("label", "Label", "text", required=False),
            _field("description", "Description", "textarea", required=False),
            _field(
                "value_type",
                "Value type",
                "select",
                choices=(
                    ("text", "Text"),
                    ("integer", "Integer"),
                    ("decimal", "Decimal"),
                    ("boolean", "Boolean"),
                    ("date", "Date"),
                    ("json", "Structured JSON"),
                ),
                help_text="Type-checks the stored JSON value.",
            ),
            _field(
                "value",
                "Value",
                "typed-value",
                help_text="Credentials and secrets must not be stored here.",
            ),
        ),
    },
    {
        "key": "academic-years",
        "label": "Academic years",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field("code", "Year code", "text"),
            _field("name", "Display name", "text"),
            _field("start_date", "Start date", "date"),
            _field("end_date", "End date", "date"),
        ),
    },
    {
        "key": "terms",
        "label": "Terms",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field(
                "academic_year",
                "Academic year",
                "relation",
                options_resource="academic-years",
            ),
            _field("code", "Term code", "text"),
            _field("name", "Display name", "text"),
            _field("sequence", "Sequence", "integer"),
            _field("start_date", "Start date", "date"),
            _field("end_date", "End date", "date"),
        ),
    },
    {
        "key": "levels",
        "label": "Educational levels",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field("code", "Level code", "text"),
            _field("name", "Display name", "text"),
            _field("position", "Display position", "integer"),
        ),
    },
    {
        "key": "classes",
        "label": "Classes",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field("level", "Educational level", "relation", options_resource="levels"),
            _field("code", "Class code", "text"),
            _field("name", "Display name", "text"),
            _field("position", "Display position", "integer"),
        ),
    },
    {
        "key": "streams",
        "label": "Streams",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field("school_class", "Class", "relation", options_resource="classes"),
            _field("code", "Stream code", "text"),
            _field("name", "Display name", "text"),
        ),
    },
    {
        "key": "subjects",
        "label": "Subject catalogue",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field("code", "Subject code", "text"),
            _field("name", "Display name", "text"),
            _field("description", "Description", "textarea", required=False),
        ),
    },
    {
        "key": "subject-offerings",
        "label": "Class and subject assignments",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field(
                "academic_year",
                "Academic year",
                "relation",
                options_resource="academic-years",
            ),
            _field(
                "term", "Term", "relation", required=False, options_resource="terms"
            ),
            _field("school_class", "Class", "relation", options_resource="classes"),
            _field(
                "stream",
                "Stream",
                "relation",
                required=False,
                options_resource="streams",
            ),
            _field("subject", "Subject", "relation", options_resource="subjects"),
        ),
    },
    {
        "key": "teaching-assignments",
        "label": "Teaching assignments",
        "endpoint": "resources",
        "permission": CONFIGURATION_MANAGE,
        "read_permission": CONFIGURATION_READ,
        "fields": (
            _field(
                "offering",
                "Class and subject",
                "relation",
                options_resource="subject-offerings",
            ),
            _field(
                "staff_membership",
                "Institution staff",
                "relation",
                options_resource="staff-memberships",
            ),
            _field("effective_from", "Effective from", "date"),
            _field("effective_until", "Effective until", "date", required=False),
        ),
    },
    {
        "key": "staff-memberships",
        "label": "Staff affiliations",
        "endpoint": "staff-memberships",
        "permission": STAFF_MANAGE,
        "read_permission": STAFF_READ,
        "fields": (
            _field(
                "user",
                "Existing account ID",
                "integer",
                help_text="Use an account provisioned through the separately approved identity process.",
            ),
            _field("staff_reference", "Staff reference", "text", required=False),
            _field("effective_from", "Effective from", "date"),
            _field("effective_until", "Effective until", "date", required=False),
        ),
    },
    {
        "key": "enrolments",
        "label": "Enrolment placements",
        "endpoint": "enrolments",
        "permission": ENROLMENT_MANAGE,
        "read_permission": ENROLMENT_READ,
        "fields": (
            _field(
                "learner_reference",
                "Learner registry ID",
                "uuid",
                help_text="Opaque ID only; learner personal data is not part of this form.",
            ),
            _field(
                "academic_year",
                "Academic year",
                "relation",
                options_resource="academic-years",
            ),
            _field("school_class", "Class", "relation", options_resource="classes"),
            _field(
                "stream",
                "Stream",
                "relation",
                required=False,
                options_resource="streams",
            ),
            _field("effective_from", "Effective from", "date"),
            _field("effective_until", "Effective until", "date", required=False),
        ),
    },
)

RELEASE_FORM_SCHEMA: tuple[dict[str, Any], ...] = (
    _field("effective_from", "Effective from", "date"),
    _field(
        "source_release",
        "Copy approved configuration",
        "relation",
        required=False,
        options_resource="approved-releases",
    ),
)

APPROVAL_SCHEMA = {
    "submit_permission": CONFIGURATION_SUBMIT,
    "approve_permission": CONFIGURATION_APPROVE,
    "read_permission": CONFIGURATION_READ,
}
