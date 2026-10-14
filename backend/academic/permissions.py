"""Unseeded, exact-institution authorization contracts. Codes are not role grants."""

CANDIDATE_READ = "academic.candidate.read"
CANDIDATE_WRITE = "academic.candidate.write"
CANDIDATE_RECONCILE = "academic.candidate.reconcile"
CANDIDATE_IMPORT = "academic.candidate.import"
GUARDIAN_READ = "academic.guardian.read"
GUARDIAN_WRITE = "academic.guardian.write"
BASELINE_READ = "academic.baseline.read"
BASELINE_ENTER = "academic.baseline.enter"
BASELINE_SUBMIT = "academic.baseline.submit"
BASELINE_APPROVE = "academic.baseline.approve"
BASELINE_CORRECT = "academic.baseline.correct"
BASELINE_CORRECTION_AUTHORIZE = "academic.baseline.correction.authorize"
WEEKLY_READ = "academic.weekly.read"
WEEKLY_SCHEDULE = "academic.weekly.schedule"
WEEKLY_ENTER = "academic.weekly.enter"
WEEKLY_REVIEW = "academic.weekly.review"
WEEKLY_APPROVE = "academic.weekly.approve"
WEEKLY_PUBLISH = "academic.weekly.publish"
WEEKLY_CORRECT = "academic.weekly.correct"
WEEKLY_CORRECTION_AUTHORIZE = "academic.weekly.correction.authorize"
MOCK_READ = "academic.mock.read"
MOCK_PREPARE = "academic.mock.prepare"
MOCK_ENTER = "academic.mock.enter"
MOCK_REVIEW = "academic.mock.review"
MOCK_APPROVE = "academic.mock.approve"
MOCK_PUBLISH = "academic.mock.publish"
MOCK_CORRECT = "academic.mock.correct"
MOCK_CORRECTION_AUTHORIZE = "academic.mock.correction.authorize"

ACTIVITY_PERMISSIONS = {
    "weekly": {
        "read": WEEKLY_READ,
        "schedule": WEEKLY_SCHEDULE,
        "enter": WEEKLY_ENTER,
        "review": WEEKLY_REVIEW,
        "approve": WEEKLY_APPROVE,
        "publish": WEEKLY_PUBLISH,
        "correct": WEEKLY_CORRECT,
        "authorize": WEEKLY_CORRECTION_AUTHORIZE,
    },
    "mock": {
        "read": MOCK_READ,
        "schedule": MOCK_PREPARE,
        "enter": MOCK_ENTER,
        "review": MOCK_REVIEW,
        "approve": MOCK_APPROVE,
        "publish": MOCK_PUBLISH,
        "correct": MOCK_CORRECT,
        "authorize": MOCK_CORRECTION_AUTHORIZE,
    },
}

# Only used to discover institutions and read academic-structure choices. Every
# operational endpoint still checks its own exact action/record permission.
ACADEMIC_ACCESS_CODES = (
    CANDIDATE_READ,
    CANDIDATE_WRITE,
    CANDIDATE_RECONCILE,
    CANDIDATE_IMPORT,
    GUARDIAN_READ,
    GUARDIAN_WRITE,
    BASELINE_READ,
    BASELINE_ENTER,
    BASELINE_SUBMIT,
    BASELINE_APPROVE,
    BASELINE_CORRECT,
    BASELINE_CORRECTION_AUTHORIZE,
    *(code for grants in ACTIVITY_PERMISSIONS.values() for code in grants.values()),
)
