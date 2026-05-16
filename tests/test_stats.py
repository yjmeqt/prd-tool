"""Tests for prd_tool.stats."""

import xml.etree.ElementTree as ET
from pathlib import Path

from prd_tool.stats import compute_prd_stats, print_stats

FIXTURES = Path(__file__).parent / "fixtures"


def test_compute_stats_minimal() -> None:
    tree = ET.parse(FIXTURES / "valid_minimal.xml")
    stats = compute_prd_stats(tree.getroot())
    assert stats["rules_done"] == 1
    assert stats["rules_total"] == 1
    assert stats["bugs_open"] == 0
    assert stats["ui_total"] == 0


def test_compute_stats_full() -> None:
    tree = ET.parse(FIXTURES / "valid_full.xml")
    stats = compute_prd_stats(tree.getroot())
    assert stats["rules_done"] == 2  # show_list=✅, tap_item=✅
    assert stats["rules_total"] == 4
    assert stats["bugs_open"] == 1  # list_scroll_crash is Open
    assert stats["ui_total"] == 1


def test_print_stats_prd() -> None:
    exit_code = print_stats(FIXTURES / "valid_minimal.xml")
    assert exit_code == 0


def test_print_stats_index(capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = print_stats(FIXTURES / "index.xml")
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "[test]" in captured.out


def test_print_stats_nonexistent() -> None:
    exit_code = print_stats(Path("/nonexistent/prd.xml"))
    assert exit_code == 1
