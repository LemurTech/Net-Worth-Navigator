"""Tests for the isolated static-demo build contract."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_builder_module():
    spec = importlib.util.spec_from_file_location(
        "build_demo_for_test", REPO_ROOT / "scripts" / "build_demo.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_uses_isolated_render_root_and_copies_only_samples(tmp_path, monkeypatch):
    builder = _load_builder_module()
    demo_dir = tmp_path / "preview"
    work_dir = tmp_path / "render-work"
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        slug = args[args.index("--scenario") + 1]
        mode_dir = work_dir / "scenarios" / slug / "deterministic"
        mode_dir.mkdir(parents=True, exist_ok=True)
        (mode_dir / "projection.html").write_text("<html></html>", encoding="utf-8")
        manifest = {
            "default_slug": "sample",
            "scenarios": [
                {"slug": name, "name": name, "modes": []}
                for name in builder.SAMPLE_SLUGS + ["private-plan"]
            ],
        }
        (work_dir / "scenarios" / "index.json").write_text(json.dumps(manifest), encoding="utf-8")

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr(builder.subprocess, "run", fake_run)
    monkeypatch.setattr(builder, "GUIDE_DIR", tmp_path / "guide")
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_demo.py", "--output-dir", str(demo_dir), "--work-dir", str(work_dir)],
    )

    builder.main()

    assert len(calls) == len(builder.SAMPLE_SLUGS)
    for args in calls:
        assert "--no-deploy" in args
        assert args[args.index("--output-root") + 1] == str(work_dir)
    manifest = json.loads((demo_dir / "scenarios" / "index.json").read_text(encoding="utf-8"))
    assert [entry["slug"] for entry in manifest["scenarios"]] == builder.SAMPLE_SLUGS
    assert not (demo_dir / "scenarios" / "private-plan").exists()
