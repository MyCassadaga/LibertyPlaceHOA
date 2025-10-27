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
