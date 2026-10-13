"""Permission identifiers for future Owner-approved institutional grants.

Codes are contracts, not seeded roles or permission assignments. Exact institution
scope keys are UUID strings checked by the existing server-side RBAC service.
"""

INSTITUTION_CREATE = "institution.create"
INSTITUTION_READ = "institution.configuration.read"
CONFIGURATION_READ = INSTITUTION_READ
CONFIGURATION_MANAGE = "institution.configuration.manage"
CONFIGURATION_SUBMIT = "institution.configuration.submit"
CONFIGURATION_APPROVE = "institution.configuration.approve"
STAFF_READ = "institution.staff.read"
STAFF_MANAGE = "institution.staff.manage"
ENROLMENT_READ = "institution.enrolment.read"
ENROLMENT_MANAGE = "institution.enrolment.manage"

RESOURCE_PERMISSION = {
    "settings": CONFIGURATION_MANAGE,
    "academic-years": CONFIGURATION_MANAGE,
    "terms": CONFIGURATION_MANAGE,
    "levels": CONFIGURATION_MANAGE,
    "classes": CONFIGURATION_MANAGE,
    "streams": CONFIGURATION_MANAGE,
    "subjects": CONFIGURATION_MANAGE,
    "subject-offerings": CONFIGURATION_MANAGE,
    "teaching-assignments": CONFIGURATION_MANAGE,
    "staff-memberships": STAFF_MANAGE,
    "enrolments": ENROLMENT_MANAGE,
}
