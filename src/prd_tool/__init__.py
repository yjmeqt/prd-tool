"""prd-tool — PRD XML validation, formatting, and stats."""

from prd_tool.cli import main
from prd_tool.format import format_prd
from prd_tool.stats import compute_prd_stats, print_stats
from prd_tool.validate import validate

__all__ = ["validate", "format_prd", "compute_prd_stats", "print_stats", "main"]
