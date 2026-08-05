from pathlib import Path

import pytest

from prd_tool.overlay import (
    OverlayError,
    PlatformRule,
    Progress,
    load_progress,
    overlay_path,
    rule_status,
)


def test_overlay_path():
    status_dir = Path("/status")
    assert overlay_path(status_dir, "auth", "login") == Path("/status/auth/login.toml")


def test_load_progress_missing_file(tmp_path: Path):
    path = tmp_path / "missing.toml"
    progress = load_progress(path)
    assert progress.rules == {}
    assert progress.notes == {}
    assert progress.platform_rules == ()


def test_load_progress_reads_data(tmp_path: Path):
    path = tmp_path / "data.toml"
    path.write_text(
        """
[rules]
"R1.1" = "✅"
"R1.2" = "⚠️"

[notes]
"R1.1" = "Done"

[[platform_rule]]
id = "PR1"
status = "✅"
description = "Platform specific"
        """
    )
    progress = load_progress(path)
    assert progress.rules == {"R1.1": "✅", "R1.2": "⚠️"}
    assert progress.notes == {"R1.1": "Done"}
    assert progress.platform_rules == (
        PlatformRule(id="PR1", status="✅", description="Platform specific"),
    )


def test_load_progress_reads_android_rule(tmp_path: Path):
    path = tmp_path / "android.toml"
    path.write_text(
        """
[[android_rule]]
id = "AR1"
status = "❌"
description = "Android specific"
        """
    )
    progress = load_progress(path)
    assert progress.platform_rules == (
        PlatformRule(id="AR1", status="❌", description="Android specific"),
    )


def test_load_progress_invalid_rule_glyph(tmp_path: Path):
    path = tmp_path / "invalid_rule.toml"
    path.write_text(
        """
[rules]
"R1.1" = "INVALID"
        """
    )
    with pytest.raises(OverlayError, match="Invalid status"):
        load_progress(path)


def test_load_progress_invalid_platform_rule_glyph(tmp_path: Path):
    path = tmp_path / "invalid_platform.toml"
    path.write_text(
        """
[[platform_rule]]
id = "PR1"
status = "INVALID"
        """
    )
    with pytest.raises(OverlayError, match="Invalid status"):
        load_progress(path)


def test_load_progress_ignores_unknown_tables(tmp_path: Path):
    path = tmp_path / "unknown.toml"
    path.write_text(
        """
[rules]
"R1.1" = "✅"

[[bug]]
id = "B1"
status = "Open"

[[ui_review]]
status = "✅"

[unknown_table]
foo = "bar"
        """
    )
    progress = load_progress(path)
    assert progress.rules == {"R1.1": "✅"}


def test_rule_status():
    progress = Progress(rules={"R1.1": "✅", "R1.2": "⚠️"}, notes={})
    assert rule_status(progress, "R1.1") == "✅"
    assert rule_status(progress, "R1.2") == "⚠️"
    assert rule_status(progress, "R1.3") == "❌"
