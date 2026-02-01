from enum import Enum

class SubstitutionType(str, Enum):
    TM_EXACT = "TM_EXACT"
    TM_FUZZY = "TM_FUZZY"
    MACHINE = "MT"
    HUMAN = "HUMAN"

class AppConstants(str, Enum):
    DEFAULT_DOMAIN = "general"
    DEFAULT_AUDIENCE = "general"
    PHARMA_DOMAIN = "pharma"
    RISK_HIGH = "high"
