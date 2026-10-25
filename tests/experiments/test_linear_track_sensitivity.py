"""The one-at-a-time sensitivity sweep of the M2a ranking (experiments/linear_track_sensitivity.py).

The quick run (two variants, two seeds, six laps) pins the files, their columns, the
variant table and the refusal of the committed directory; the numbers of a quick run
mean nothing. The full sweep is reported in docs/m2a_linear_track.md.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from experiments import linear_track_replay as lt
from experiments import linear_track_sensitivity as ls


def _read(path: Path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_every_variant_changes_one_parameter_from_the_fixed_evaluation() -> None:
    base = lt.TrackConfig()
    assert ls.VARIANTS["base"][2] == base
    for name, (parameter, value, cfg) in ls.VARIANTS.items():
        if name == "base":
            continue
        diff = {k for k in base.to_dict() if base.to_dict()[k] != cfg.to_dict()[k]}
        if parameter == "temperature":
            assert diff == {"temperature", "forward_prior"}  # the prior is rescaled to keep the untrained turn probability
            assert cfg.untrained_turn_probability() == pytest.approx(0.2)
        elif parameter == "untrained_turn_probability":
            assert diff == {"forward_prior"} and cfg.untrained_turn_probability() == pytest.approx(value)
        else:
            assert diff == {parameter} and getattr(cfg, parameter) == value
    assert ls._prior_for(0.2, 0.1) == pytest.approx(base.forward_prior)
    assert len(ls.VARIANTS) == 11


def test_quick_run_writes_the_tables_and_refuses_the_committed_directory(tmp_path, monkeypatch) -> None:
    out = tmp_path / "sens"
    result = ls.main(["--quick", "--seeds", "2", "--variants", "base,gain_20", "--workers", "1", "--out", str(out)])
    assert {p.name for p in out.iterdir()} == set(ls.OUTPUT_FILES)
    effects = _read(out / "sensitivity_effects.csv")
    assert list(effects[0]) == list(ls.EFFECT_COLUMNS)
    assert len(effects) == 2 * len(lt.COMPARISONS) and {r["variant"] for r in effects} == {"base", "gain_20"}
    summary = _read(out / "sensitivity_summary.csv")
    assert list(summary[0]) == list(ls.SUMMARY_COLUMNS) and [r["variant"] for r in summary] == ["base", "gain_20"]
    assert summary[0]["laps"] == "6" and summary[0]["lap_cap"] == "300"
    assert all(set(r["ordering_by_mean_total_steps"].split(" < ")) == set(lt.CONDITIONS) for r in summary)
    assert summary[1]["parameter"] == "value_gain" and float(summary[1]["value"]) == 20.0
    assert math.isnan(float(summary[0]["value"]))
    m = json.loads((out / "sensitivity_manifest.json").read_text())
    assert m["protocol"] == "linear_track_sensitivity" and m["quick"] is True and m["full_evaluation"] is False
    assert set(m["variants"]) == {"base", "gain_20"} and m["variants"]["gain_20"]["config"]["value_gain"] == 20.0
    assert len(result["summaries"]) == 2
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        ls.main(["--quick", "--seeds", "2", "--variants", "base"])
    with pytest.raises(SystemExit):
        ls.main(["--variants", "base,bogus", "--seeds", "1", "--out", str(tmp_path / "x")])
    assert not (tmp_path / "docs").exists()
