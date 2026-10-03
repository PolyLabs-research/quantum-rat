"""tools/update_determinism_baseline.py: the guards around the committed baselines.

The legacy set is never re-recorded (docs/decisions.md G22; docs/determinism.md),
so ``--profile legacy`` is refused unless ``--out-dir`` points elsewhere; the
research set (the default profile) needs ``--i-know-what-im-doing`` to be
overwritten in place; and ``--out-dir`` needs no flag at all, because nothing
committed is touched. Short traces (``--ticks 5``) keep these fast; the files'
content is the gate's own business (``test_trace_hash*.py``).
"""

from __future__ import annotations

import json

import pytest

from core.determinism import BASELINE_DIR, HASH_KINDS
from tools import update_determinism_baseline as tool

FILES = {
    "legacy": {"baseline_hashes.json", "baseline_behaviour_legacy.json", "baseline_physics_legacy.json",
               "baseline_meta.json", "reference_trace_legacy.jsonl"},
    "research": {"baseline_hashes_research.json", "baseline_behaviour_research.json",
                 "baseline_physics_research.json", "baseline_meta_research.json", "reference_trace_research.jsonl"},
}


def _mtimes():
    return {p.name: p.stat().st_mtime_ns for p in BASELINE_DIR.iterdir()}


def test_the_default_profile_is_research_and_the_committed_set_needs_the_flag(capsys):
    before = _mtimes()
    with pytest.raises(SystemExit) as info:
        tool.main([])
    assert "i-know-what-im-doing" in str(info.value)
    assert _mtimes() == before  # nothing written


def test_the_legacy_set_is_refused_in_place_even_with_the_flag(capsys):
    before = _mtimes()
    for argv in (["--profile", "legacy"], ["--profile", "legacy", "--i-know-what-im-doing"]):
        with pytest.raises(SystemExit) as info:
            tool.main(argv)
        assert info.value.code == 2
        assert "G22" in capsys.readouterr().err
    assert _mtimes() == before
    assert "--out-dir" in tool.LEGACY_RULE and "G22" in tool.LEGACY_RULE


@pytest.mark.parametrize("profile", ["legacy", "research"])
def test_out_dir_writes_a_profiles_five_files_without_any_flag(profile, tmp_path, capsys):
    before = _mtimes()
    tool.main(["--profile", profile, "--out-dir", str(tmp_path), "--ticks", "5"])
    assert {p.name for p in tmp_path.iterdir()} == FILES[profile]
    assert _mtimes() == before  # the committed files are untouched
    meta = json.loads((tmp_path / ("baseline_meta.json" if profile == "legacy" else "baseline_meta_research.json")).read_text())
    assert meta["profile"] == profile and meta["ticks"] == 5 and meta["hash_kinds"] == list(HASH_KINDS)
    for kind in HASH_KINDS:
        rows = json.loads((tmp_path / meta["files"][kind]).read_text())
        assert [r["tick"] for r in rows] == [0, 1, 2, 3, 4, "run"]
    assert f"profile={profile}" in capsys.readouterr().out


def test_out_dir_that_is_the_committed_directory_counts_as_in_place(capsys):
    before = _mtimes()
    with pytest.raises(SystemExit) as info:
        tool.main(["--profile", "legacy", "--out-dir", str(BASELINE_DIR)])
    assert info.value.code == 2
    with pytest.raises(SystemExit):
        tool.main(["--out-dir", str(BASELINE_DIR)])  # research without the flag
    assert _mtimes() == before
