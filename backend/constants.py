DEFAULT_ROLES = [
    ("HOMEOWNER", "Homeowner portal access"),
    ("BOARD", "Board member with elevated privileges"),
    ("TREASURER", "Treasurer responsible for billing and finance"),
    ("SECRETARY", "Secretary responsible for records and communications"),
    ("ARC", "Architectural Review Committee member"),
    ("AUDITOR", "Auditor/CPA with read access to financial records"),
    ("ATTORNEY", "Attorney with access to legal documents"),
    ("SYSADMIN", "System administrator with full access"),
]

# Higher number means more privileges
ROLE_PRIORITY = {
    "HOMEOWNER": 10,
    "ARC": 20,
    "SECRETARY": 30,
    "ATTORNEY": 35,
    "BOARD": 40,
    "TREASURER": 50,
    "AUDITOR": 60,
    "SYSADMIN": 100,
}

DEFAULT_LATE_FEE_POLICY = {
    "name": "default",
    "grace_period_days": 5,
    "dunning_schedule_days": [5, 15, 30],
    "tiers": [
        {
            "sequence_order": 1,
            "trigger_days_after_grace": 0,
            "fee_type": "flat",
            "fee_amount": 15.00,
            "fee_percent": 0,
            "description": "Initial late fee after grace period",
        },
        {
            "sequence_order": 2,
            "trigger_days_after_grace": 15,
            "fee_type": "flat",
            "fee_amount": 25.00,
            "fee_percent": 0,
            "description": "Second-tier late fee",
        },
    ],
}

CORS_ALLOW_ORIGINS = [
    "https://app.libertyplacehoa.com",
    "https://www.libertyplacehoa.com",
    "https://libertyplacehoa.com",
]
