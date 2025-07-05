"""
EFR Pipeline Module

This module handles the complete pipeline from transcript to EFR storage:
1. Data extraction from transcripts
2. EFR database storage
3. Eligibility checking with Prolog
4. Gap analysis and clarification generation
"""

# Only import modules that actually exist
try:
    from .data_extractor import DataExtractor
except ImportError:
    pass

try:
    from .efr_to_prolog_mapper import EFRToPrologMapper
except ImportError:
    pass

try:
    from .clarification_generator import ClarificationGenerator
except ImportError:
    pass

__all__ = [
    'DataExtractor',
    'EFRToPrologMapper',
    'ClarificationGenerator'
] 