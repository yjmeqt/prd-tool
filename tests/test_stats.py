"""Tests for prd_tool.stats."""

import xml.etree.ElementTree as ET
from pathlib import Path

from prd_tool.overlay import PlatformRule, Progress
from prd_tool.stats import compute_prd_stats, has_unfinished_work, print_stats

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


def test_has_unfinished_work_minimal() -> None:
    # valid_minimal.xml has one rule with status ✅, no bugs — fully done.
    tree = ET.parse(FIXTURES / "valid_minimal.xml")
    assert has_unfinished_work(tree.getroot()) is False


def test_has_unfinished_work_full() -> None:
    # valid_full.xml has rules in mixed states + an Open bug — unfinished.
    tree = ET.parse(FIXTURES / "valid_full.xml")
    assert has_unfinished_work(tree.getroot()) is True


def test_print_stats_unfinished_filters_index(capsys, tmp_path) -> None:  # type: ignore[no-untyped-def]
    # Build a fake index where one entry has unfinished work and one does not.
    done = (
        '<prd name="Done">'
        '<requirement id="R1" name="x"><description>d</description>'
        '<rule id="r" status="✅">all good</rule>'
        "</requirement></prd>"
    )
    unfinished = (
        '<prd name="Wip">'
        '<requirement id="R1" name="x"><description>d</description>'
        '<rule id="r" status="❌">todo</rule>'
        "</requirement></prd>"
    )
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "alpha" / "done.xml").write_text(done, encoding="utf-8")
    (tmp_path / "beta" / "wip.xml").write_text(unfinished, encoding="utf-8")
    (tmp_path / "index.xml").write_text(
        "<prd_index>"
        '<module name="alpha"><entry file="alpha/done.xml" name="Done"/></module>'
        '<module name="beta"><entry file="beta/wip.xml" name="Wip"/></module>'
        "</prd_index>",
        encoding="utf-8",
    )
    exit_code = print_stats(tmp_path / "index.xml", unfinished_only=True)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "[beta]" in out and "Wip:" in out
    # Done module/feature should be entirely omitted, not just the row.
    assert "[alpha]" not in out
    assert "Done:" not in out


def test_print_stats_unfinished_on_done_prd_returns_no_output(capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = print_stats(FIXTURES / "valid_minimal.xml", unfinished_only=True)
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_progress_overlay() -> None:
    xml = """
    <prd name="test">
        <requirement id="R1" name="req">
            <description>desc</description>
            <rule id="a">Rule A</rule>
            <rule id="b">Rule B</rule>
        </requirement>
    </prd>
    """
    root = ET.fromstring(xml)

    # 1. XML rules without status + Progress with one ✅ and one missing -> done=1 total=2
    progress = Progress(
        rules={"R1.a": "✅"},
        notes={},
        platform_rules=(),
    )
    stats = compute_prd_stats(root, progress)
    assert stats["rules_total"] == 2
    assert stats["rules_done"] == 1

    # 3. has_unfinished True when a rule missing from overlay
    assert has_unfinished_work(root, progress) is True

    # 2. has_unfinished False when all overlay ✅ (incl. covering all XML rules)
    progress_all_done = Progress(
        rules={"R1.a": "✅", "R1.b": "✅"},
        notes={},
        platform_rules=(),
    )
    assert has_unfinished_work(root, progress_all_done) is False
    stats_all_done = compute_prd_stats(root, progress_all_done)
    assert stats_all_done["rules_done"] == 2
    assert stats_all_done["rules_total"] == 2

    # 4. platform_rules counted in totals
    progress_with_pr = Progress(
        rules={"R1.a": "✅", "R1.b": "✅"},
        notes={},
        platform_rules=(
            PlatformRule(id="pr1", status="✅"),
            PlatformRule(id="pr2", status="❌"),
        ),
    )
    stats_pr = compute_prd_stats(root, progress_with_pr)
    assert stats_pr["rules_total"] == 4  # 2 XML rules + 2 platform rules
    assert stats_pr["rules_done"] == 3  # R1.a, R1.b, pr1

    assert has_unfinished_work(root, progress_with_pr) is True
