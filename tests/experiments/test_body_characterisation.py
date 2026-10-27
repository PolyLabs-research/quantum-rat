"""The body characterisation (experiments.body_characterisation), on a quick run (M3 step 1, G44)."""

import json

import pytest

from experiments import body_characterisation as bc


@pytest.fixture(scope="module")
def quick(tmp_path_factory):
    out = tmp_path_factory.mktemp("body")
    return out, bc.main(["--quick", "--workers", "1", "--n-boot", "200", "--out", str(out)])


def test_quick_run_writes_its_files_and_scores_t1(quick) -> None:
    out, payload = quick
    assert set(bc.OUTPUT_FILES) <= {p.name for p in out.iterdir()}
    assert set(payload["summary"]) == {"discrete", "rodent_quiet", "rodent"} and payload["exploratory"] is True
    for entry in payload["summary"].values():
        assert set(entry["track"]) == set(bc.METRICS["track"]) and set(entry["open"]) == set(bc.METRICS["open"])
        assert isinstance(entry["T1"]["passes"], bool) and entry["T1"]["lap_bound"] == 36
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["exploratory"] is True and manifest["conditions"]["rodent"]["body.model"] == "rodent"


def test_a_run_is_deterministic_and_the_committed_directory_is_refused(tmp_path, monkeypatch) -> None:
    a = bc.run_one(("rodent", dict(bc.DEFAULT_CONDITIONS["rodent"]), 3, 120))
    b = bc.run_one(("rodent", dict(bc.DEFAULT_CONDITIONS["rodent"]), 3, 120))
    assert a == b
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        bc.main(["--quick", "--out", "docs/data/m3/body"])
