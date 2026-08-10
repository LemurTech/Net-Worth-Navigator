#!/usr/bin/env python3
"""
build_demo.py — Build the full gh-pages demo from sample scenarios.

Usage:
    python scripts/build_demo.py

Steps:
  1. Re-render all sample scenarios (deterministic + historical + monte carlo)
  2. Filter manifest to sample-only (no personal data)
  3. Build static read-only setup pages for each scenario
  4. Build demo shell page, compare page, and definitions page
  5. Build the Starlight User Guide site (if available)
  6. Assemble everything under output/demo/
  7. (Optional) Deploy to gh-pages with --deploy flag

All generated files go under output/demo/.  Copy or symlink them into
the gh-pages branch 'demo/' directory for deployment.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "output"
DEFAULT_DEMO_DIR = OUTPUT / "demo"
DEFAULT_WORK_DIR = OUTPUT / "demo-build-work"
SAMPLE_SLUGS = ["sample", "sample-a", "sample-b", "sample-couples"]
GUIDE_DIR = REPO_ROOT / "docs" / "guide"


def step(msg: str) -> None:
    print(f"\n==> {msg}")


def _resolve_path(raw: str | None, default: Path) -> Path:
    path = Path(raw) if raw else default
    return path if path.is_absolute() else REPO_ROOT / path


def _venv_python() -> Path | None:
    for candidate in (
        REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return candidate
    return None


def _prepare_empty_dir(path: Path, *, label: str) -> None:
    resolved = path.resolve()
    if resolved in {REPO_ROOT.resolve(), OUTPUT.resolve()}:
        raise ValueError(f"Refusing to replace {label} at {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Build the gh-pages demo")
    parser.add_argument("--deploy", action="store_true", help="Deploy to gh-pages branch after building")
    parser.add_argument("--output-dir", help="Static demo destination (default: output/demo)")
    parser.add_argument("--work-dir", help="Isolated temporary render directory (default: output/demo-build-work)")
    args = parser.parse_args()

    demo_dir = _resolve_path(args.output_dir, DEFAULT_DEMO_DIR)
    work_dir = _resolve_path(args.work_dir, DEFAULT_WORK_DIR)
    if demo_dir.resolve() == work_dir.resolve():
        parser.error("--output-dir and --work-dir must be different directories")
    _prepare_empty_dir(demo_dir, label="demo output")
    _prepare_empty_dir(work_dir, label="demo work directory")

    python = str(_venv_python() or sys.executable)

    # ── 1. Re-render sample scenarios ────────────────────────────────────
    step("Re-rendering sample scenarios...")
    for slug in SAMPLE_SLUGS:
        result = subprocess.run(
            [
                python, "run.py", "--offline", "--no-deploy",
                "--output-root", str(work_dir), "--scenario", slug,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            print(f"  ERROR rendering {slug}: exit={result.returncode}", flush=True)
            print(f"  stderr:\n{result.stderr}", flush=True)
            sys.exit(1)
        print(f"  {slug}: OK")

    # ── 2. Filter manifest to sample-only ────────────────────────────────
    step("Filtering manifest to sample-only scenarios...")
    manifest_path = work_dir / "scenarios" / "index.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["scenarios"] = [e for e in manifest["scenarios"] if e.get("slug") in SAMPLE_SLUGS]

    # Copy only public sample artifacts. The work directory is disposable and
    # leaves normal output/scenarios, caches, and personal sidecars untouched.
    demo_scenarios = demo_dir / "scenarios"
    demo_scenarios.mkdir()
    for slug in SAMPLE_SLUGS:
        source = work_dir / "scenarios" / slug
        if not source.exists():
            raise FileNotFoundError(f"Sample render was not created: {source}")
        shutil.copytree(source, demo_scenarios / slug)
    (demo_scenarios / "index.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  Demo scenarios: {len(manifest['scenarios'])}")

    # ── 3. Build static read-only setup pages ────────────────────────────
    step("Building static read-only setup pages...")
    sys.path.insert(0, str(REPO_ROOT))
    from src.demo_setup_page import build_demo_setup_page  # noqa: E402

    # Build name map from TOML files
    import tomllib
    scenario_names = {}
    for slug in SAMPLE_SLUGS:
        cfg_path = REPO_ROOT / "scenarios" / f"{slug}.toml"
        if cfg_path.exists():
            cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
            scenario_names[slug] = cfg.get("scenario", {}).get("name", slug)
        else:
            scenario_names[slug] = slug
    scenario_options = [(s, scenario_names[s]) for s in SAMPLE_SLUGS]

    for slug in SAMPLE_SLUGS:
        config_path = REPO_ROOT / "scenarios" / f"{slug}.toml"
        if config_path.exists():
            build_demo_setup_page(
                config_path=config_path,
                output_path=demo_dir / "scenarios" / slug / "setup.html",
                slug=slug,
                scenario_options=scenario_options,
                setup_relbase="../",
                back_relbase="../../",
            )
            print(f"  {slug}/setup.html")

    # Default setup page (sample scenario)
    build_demo_setup_page(
        config_path=REPO_ROOT / "scenarios" / "sample.toml",
        output_path=demo_dir / "setup.html",
        slug="sample",
        scenario_options=scenario_options,
        setup_relbase="./scenarios/",
    )
    print("  demo/setup.html (default)")

    # ── 4. Build shell, compare, and definitions pages ───────────────────
    step("Building shell page, compare page, and definitions...")
    from src.scenario_shell import build_scenario_shell, build_compare_page  # noqa: E402
    from src.definitions_page import build_definitions_page_html  # noqa: E402

    manifest = json.loads((demo_dir / "scenarios" / "index.json").read_text())

    build_scenario_shell(
        manifest=manifest,
        output_path=demo_dir / "projection.html",
        manifest_relpath="scenarios/index.json",
        setup_url="./setup.html",
        definitions_url="./definitions.html",
    )
    print("  projection.html")

    build_compare_page(
        manifest=manifest,
        output_path=demo_dir / "compare.html",
        manifest_relpath="scenarios/index.json",
        shell_url="./projection.html",
        definitions_url="./definitions.html",
    )
    print("  compare.html")

    defs = build_definitions_page_html(
        editor_url="./setup.html",
        projection_url="https://lemurtech.github.io/Net-Worth-Navigator/demo/projection.html",
    )
    (demo_dir / "definitions.html").write_text(defs)
    print("  definitions.html")

    # ── 5. Build Starlight User Guide (if available) ─────────────────────
    if (GUIDE_DIR / "node_modules").exists() and (GUIDE_DIR / "package.json").exists():
        step("Building Starlight User Guide...")
        result = subprocess.run(
            ["npx", "astro", "build"],
            cwd=str(GUIDE_DIR),
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            print("  Starlight build OK")
        else:
            print(f"  Starlight build failed: {result.stderr[:300]}")
    else:
        print("  Skipping Starlight (node_modules not found)")

    # ── 6. Final output ──────────────────────────────────────────────────
    step("Demo build complete")
    print(f"  Output: {demo_dir}")
    print(f"  Preview: python -m http.server 8000 --directory {demo_dir}")
    print(f"  Total size: {sum(f.stat().st_size for f in demo_dir.rglob('*') if f.is_file()) / 1024:.0f} KB")
    print()
    print("  To deploy to gh-pages:")
    print("    1. Clone the gh-pages branch to a worktree:")
    print("         git worktree add /tmp/deploy gh-pages")
    print("    2. Copy the demo directory:")
    print("         cp -r output/demo/* /tmp/deploy/demo/")
    print("         cp -r docs/guide/dist/* /tmp/deploy/")
    print("         touch /tmp/deploy/.nojekyll")
    print("    3. Commit and push:")
    print("         cd /tmp/deploy && git add -A && git commit -m 'rebuild demo'")
    print("         git push origin gh-pages")
    print("    4. Clean up:")
    print("         cd / && git worktree remove /tmp/deploy")

    if args.deploy:
        step("Deploying to gh-pages...")
        import subprocess as sp
        sp.run(["git", "worktree", "remove", "/tmp/nwn-demo-deploy"], capture_output=True)
        sp.run(["git", "fetch", "origin", "gh-pages"], cwd=str(REPO_ROOT))
        result = sp.run(
            ["git", "worktree", "add", "/tmp/nwn-demo-deploy", "gh-pages"],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  Worktree error: {result.stderr}")
            sys.exit(1)

        deploy_dir = Path("/tmp/nwn-demo-deploy")

        # Copy Starlight build
        if (GUIDE_DIR / "dist").exists():
            for f in (GUIDE_DIR / "dist").iterdir():
                if f.is_dir():
                    shutil.copytree(f, deploy_dir / f.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(f, deploy_dir / f.name)

        # Copy demo files
        shutil.copytree(demo_dir, deploy_dir / "demo", dirs_exist_ok=True)

        # Ensure .nojekyll
        (deploy_dir / ".nojekyll").touch()

        sp.run(["git", "add", "-A"], cwd=str(deploy_dir))
        sp.run(
            ["git", "commit", "-m", "demo: rebuild from build_demo.py"],
            cwd=str(deploy_dir),
        )
        sp.run(["git", "push", "origin", "gh-pages"], cwd=str(deploy_dir))
        sp.run(["git", "worktree", "remove", "/tmp/nwn-demo-deploy"])
        print("  Deployed!")


if __name__ == "__main__":
    main()
