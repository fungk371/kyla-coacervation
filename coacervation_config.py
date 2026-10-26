"""
Configuration for the coacervation app.

To add a new submission metadata field, add one entry to METADATA_FIELDS.
Supported types: 'text', 'textarea', 'number'. Set 'required': True to enforce
it at submission (the app bounces back submissions missing required fields).
"""

METADATA_FIELDS = [
    {"key": "sample_id", "label": "Sample ID (key_id1)", "type": "text",
     "required": True, "help": "Nexus sample key, e.g. S-20250717-04620"},
    {"key": "purpose", "label": "Purpose / Request description",
     "type": "textarea", "required": True,
     "help": "What is this sample and why do we need the data?"},
    {"key": "submitter", "label": "Submitter", "type": "text", "required": True},
    {"key": "study", "label": "Study / Project", "type": "text", "required": False},
    {"key": "surfactant_name", "label": "Surfactant type", "type": "text", "required": False},
    {"key": "surfactant_pct", "label": "Surfactant concentration (%)",
     "type": "number", "required": False},
    {"key": "polymer_name", "label": "Polymer type", "type": "text", "required": False},
    {"key": "polymer_pct", "label": "Polymer concentration (%)",
     "type": "number", "required": False},
    {"key": "salt_mM", "label": "Salt / ionic strength (mM)",
     "type": "number", "required": False},
    {"key": "temperature_c", "label": "Temperature (°C)",
     "type": "number", "required": False},
    # --- add more fields here as needed ---
]

# Databricks XY-table target for the eventual flex-driver push.
NEXUS_XY_TARGET = "cdl_stc_prod.silver_nexus.nexus_xy"

# Local SQLite store for submissions (used until Databricks access is granted).
SUBMISSIONS_DB = "coacervation_submissions.db"
