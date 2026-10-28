"""Data Stewardship Toolkit.

A small, dependency-light toolkit that enforces reproducible data
stewardship: every dataset must have an inventory entry, metadata, a
registered licence and a verified checksum, and every published figure
must trace back to a versioned dataset input.
"""

__version__ = "1.0.0"

from .checks import StewardshipReport, run_all_checks  # noqa: F401
from .ingest import ingest_dataset, register_figure  # noqa: F401
