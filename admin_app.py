from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import threading
import tomllib
import tomlkit
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from src.config_loader import merge_tax_tables, TAX_TABLES_DIR
from src.csv_importer import accounts_from_csv, merge_accounts, parse_csv
from src.definitions_page import build_definitions_page_html
from src.scenarios import create_scenario_from_content, discover_scenarios, get_scenario, normalized_render_modes, SCENARIOS_DIR, write_scenarios_index
from src.scenario_shell import build_scenario_shell, build_compare_page

APP_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = APP_ROOT / "output"
VENV_PYTHON = APP_ROOT / ".venv" / "bin" / "python"
PYTHON_BIN = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
RUN_SCRIPT = APP_ROOT / "run.py"
PUBLIC_PROJECTION_URL = "http://casalemuria.lan/finances/projection.html"
PUBLIC_EDITOR_URL = "http://casalemuria.lan/finances/config/setup"
PUBLIC_DEFINITIONS_URL = "http://casalemuria.lan/finances/definitions.html"

app = FastAPI(title="Net Worth Navigator Config Editor")
templates = Jinja2Templates(directory=str(APP_ROOT / "templates"))
RENDER_JOBS: dict[str, dict] = {}
RENDER_JOBS_LOCK = threading.Lock()


def _current_scenario(scenario_slug: str | None = None):
    return get_scenario(scenario_slug)


def _config_path(scenario_slug: str | None = None) -> Path:
    return _current_scenario(scenario_slug).config_path


def _backup_dir(scenario_slug: str | None = None) -> Path:
    return OUTPUT_DIR / "config-backups" / _current_scenario(scenario_slug).slug


def _read_config_text(scenario_slug: str | None = None) -> str:
    return _config_path(scenario_slug).read_text(encoding="utf-8")


def _prune_backups(backup_dir: Path, keep_days: int = 14, keep_min: int = 5) -> None:
    """Remove backups older than keep_days, but always keep the keep_min most recent."""
    cutoff = datetime.now() - timedelta(days=keep_days)
    cutoff_ts = cutoff.timestamp()
    backups = sorted(
        backup_dir.glob("config-*.toml"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    # Always protect the keep_min most recent, regardless of age
    protected = set(backups[:keep_min])
    for backup in backups:
        if backup in protected:
            continue
        try:
            if backup.stat().st_mtime < cutoff_ts:
                backup.unlink(missing_ok=True)
        except OSError:
            pass


def _validate_config_text(content: str) -> dict:
    if not content.strip():
        raise ValueError("Configuration cannot be empty.")
    return merge_tax_tables(tomllib.loads(content))


def _last_backup_content(backup_dir: Path) -> str | None:
    """Return content of the most recent backup, or None if no backups exist."""
    backups = sorted(
        backup_dir.glob("config-*.toml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        return None
    try:
        return backups[0].read_text(encoding="utf-8")
    except Exception:
        return None


def _backup_and_write(content: str, scenario_slug: str | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    backup_dir = _backup_dir(scenario_slug)
    backup_dir.mkdir(parents=True, exist_ok=True)

    current_content = _read_config_text(scenario_slug)

    # Deduplicate: skip creating a new backup if the last backup matches current state
    last_content = _last_backup_content(backup_dir)
    if last_content is not None and last_content == current_content:
        backups = sorted(
            backup_dir.glob("config-*.toml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        backup_path = backups[0]
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"config-{ts}.toml"
        backup_path.write_text(current_content, encoding="utf-8")

    _config_path(scenario_slug).write_text(content, encoding="utf-8")
    # fsync to flush through bind-mount / Docker storage delay
    config_path = _config_path(scenario_slug)
    fd = os.open(str(config_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    _prune_backups(backup_dir)
    return backup_path


def _render_projection_offline(scenario_slug: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [str(PYTHON_BIN), str(RUN_SCRIPT), "--offline"]
    if scenario_slug:
        command.extend(["--scenario", scenario_slug])
    return subprocess.run(
        command,
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )


def _render_projection_offline_streaming(
    scenario_slug: str | None = None,
    *,
    line_callback=None,
) -> subprocess.CompletedProcess[str]:
    command = [str(PYTHON_BIN), str(RUN_SCRIPT), "--offline"]
    if scenario_slug:
        command.extend(["--scenario", scenario_slug])
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        command,
        cwd=str(APP_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    stdout_lines: list[str] = []
    if process.stdout is not None:
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            stdout_lines.append(line)
            if line_callback is not None:
                line_callback(line)
    stderr_text = process.stderr.read() if process.stderr is not None else ""
    returncode = process.wait(timeout=300)
    return subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout="\n".join(stdout_lines),
        stderr=stderr_text,
    )


def _render_all_scenarios() -> list[tuple[str, subprocess.CompletedProcess[str]]]:
    results = []
    for scenario in discover_scenarios():
        results.append((scenario.slug, _render_projection_offline(scenario.slug)))
    return results


def _build_context(request: Request, *, content: str, status_kind: str = "info",
                   status_title: str | None = None, status_message: str | None = None,
                   details: str | None = None, backup_path: str | None = None,
                   scenario_slug: str | None = None,
                   last_action: str = "",
                   clone_name: str = "",
                   clone_slug: str = "",
                   clone_description: str = "") -> dict:
    scenario = _current_scenario(scenario_slug)
    resolved_slug = scenario.slug
    config_path = _config_path(resolved_slug)
    discovered_scenarios = discover_scenarios()
    # Split into user scenarios and sample/demo scenarios
    user_scenarios = []
    sample_scenarios = []
    for opt in discovered_scenarios:
        name_lower = (opt.name or "").strip().lower()
        if name_lower.startswith("sample"):
            sample_scenarios.append(opt)
        else:
            user_scenarios.append(opt)

    scenario_options = [
        {
            "slug": option.slug,
            "name": option.name,
            "description": option.description,
            "is_default": option.is_default,
        }
        for option in user_scenarios
    ]
    sample_options = [
        {
            "slug": option.slug,
            "name": option.name,
            "description": option.description,
            "is_default": option.is_default,
        }
        for option in sample_scenarios
    ]
    last_modified = datetime.fromtimestamp(config_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    render_plan = _render_plan_snapshot(
        content=content,
        scenario_slug=resolved_slug,
        scenario_name=scenario.name,
        discovered_scenarios=discovered_scenarios,
    )
    return {
        "request": request,
        "content": content,
        "status_kind": status_kind,
        "status_title": status_title,
        "status_message": status_message,
        "details": details,
        "backup_path": backup_path,
        "last_action": last_action,
        "backup_dir": str(_backup_dir(resolved_slug)),
        "config_path": str(config_path),
        "scenario_name": scenario.name,
        "scenario_slug": resolved_slug,
        "scenario_description": scenario.description,
        "scenario_options": scenario_options,
        "sample_options": sample_options,
        "render_plan_json": json.dumps(render_plan),
        "clone_name": clone_name,
        "clone_slug": clone_slug,
        "clone_description": clone_description,
        "last_modified": last_modified,
        "projection_url": f"{PUBLIC_PROJECTION_URL}?scenario={resolved_slug}",
        "editor_url": f"{PUBLIC_EDITOR_URL}?scenario={resolved_slug}",
        "definitions_url": PUBLIC_DEFINITIONS_URL,
    }


def _render_modes_from_content(content: str | None, fallback_slug: str | None = None) -> list[str]:
    if content:
        try:
            parsed = tomllib.loads(content)
            simulation_cfg = parsed.get("simulation", {}) if isinstance(parsed, dict) else {}
            if isinstance(simulation_cfg, dict):
                return normalized_render_modes(simulation_cfg.get("render_modes"))
        except Exception:
            pass
    if fallback_slug:
        try:
            parsed = tomllib.loads(_read_config_text(fallback_slug))
            simulation_cfg = parsed.get("simulation", {}) if isinstance(parsed, dict) else {}
            if isinstance(simulation_cfg, dict):
                return normalized_render_modes(simulation_cfg.get("render_modes"))
        except Exception:
            pass
    return normalized_render_modes(None)


def _render_plan_snapshot(
    *,
    content: str,
    scenario_slug: str,
    scenario_name: str,
    discovered_scenarios,
) -> dict:
    current_modes = _render_modes_from_content(content, fallback_slug=scenario_slug)
    scenarios_summary = []
    total_render_count = 0
    for discovered in discovered_scenarios:
        try:
            modes = _render_modes_from_content(None, fallback_slug=discovered.slug)
        except Exception:
            modes = normalized_render_modes(None)
        total_render_count += len(modes)
        scenarios_summary.append(
            {
                "slug": discovered.slug,
                "name": discovered.name,
                "render_modes": modes,
                "render_count": len(modes),
            }
        )

    return {
        "current_scenario_slug": scenario_slug,
        "current_scenario_name": scenario_name,
        "current_render_modes": current_modes,
        "current_render_count": len(current_modes),
        "scenario_count": len(scenarios_summary),
        "total_render_count": total_render_count,
        "scenario_names": [item["name"] for item in scenarios_summary],
        "scenarios": scenarios_summary,
    }


def _store_render_job(job: dict) -> dict:
    with RENDER_JOBS_LOCK:
        RENDER_JOBS[job["id"]] = job
    return job


def _get_render_job(job_id: str) -> dict | None:
    with RENDER_JOBS_LOCK:
        job = RENDER_JOBS.get(job_id)
        return dict(job) if job is not None else None


def _update_render_job(job_id: str, **fields) -> dict | None:
    with RENDER_JOBS_LOCK:
        job = RENDER_JOBS.get(job_id)
        if job is None:
            return None
        job.update(fields)
        job["updated_at"] = datetime.now().isoformat()
        return dict(job)


def _job_redirect_url(scenario_slug: str, job_id: str) -> str:
    return f"{PUBLIC_EDITOR_URL}?scenario={scenario_slug}&job={job_id}"


def _job_status_payload(job: dict) -> dict:
    return {
        "job_id": job["id"],
        "action": job["action"],
        "state": job["state"],
        "scenario_slug": job["scenario_slug"],
        "scenario_count": job["scenario_count"],
        "total_render_count": job["total_render_count"],
        "current_scenario_index": job.get("current_scenario_index", 0),
        "current_scenario_name": job.get("current_scenario_name", ""),
        "current_mode_index": job.get("current_mode_index", 0),
        "current_mode": job.get("current_mode", ""),
        "completed_render_count": job.get("completed_render_count", 0),
        "title": job.get("title", ""),
        "detail": job.get("detail", ""),
        "progress": job.get("progress", ""),
        "status_kind": job.get("status_kind", "info"),
        "status_title": job.get("status_title"),
        "status_message": job.get("status_message"),
        "details": job.get("details"),
        "failed_scenarios": job.get("failed_scenarios"),
        "backup_path": job.get("backup_path"),
        "last_action": job.get("last_action", ""),
        "redirect_url": _job_redirect_url(job["scenario_slug"], job["id"]),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
    }


def _create_render_job(
    *,
    action: str,
    scenario_slug: str,
    scenario_count: int,
    total_render_count: int,
    backup_path: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    return _store_render_job(
        {
            "id": uuid4().hex,
            "action": action,
            "state": "queued",
            "scenario_slug": scenario_slug,
            "scenario_count": scenario_count,
            "total_render_count": total_render_count,
            "current_scenario_index": 0,
            "current_scenario_name": "",
            "current_mode_index": 0,
            "current_mode": "",
            "completed_render_count": 0,
            "title": "Queued render job",
            "detail": f"{scenario_count} scenario(s), {total_render_count} mode page(s)",
            "progress": "Waiting for background worker…",
            "status_kind": "info",
            "status_title": None,
            "status_message": None,
            "details": None,
            "backup_path": backup_path,
            "last_action": action,
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
        }
    )


def _job_context_from_completed_job(job_id: str) -> dict | None:
    job = _get_render_job(job_id)
    if job is None or job.get("state") not in {"completed", "failed"}:
        return None
    return {
        "status_kind": job.get("status_kind", "info"),
        "status_title": job.get("status_title"),
        "status_message": job.get("status_message"),
        "details": job.get("details"),
        "backup_path": job.get("backup_path"),
        "last_action": job.get("last_action", ""),
    }


def _planned_modes_for_scenario(slug: str) -> list[str]:
    return _render_modes_from_content(None, fallback_slug=slug)


def _run_single_scenario_job(
    *,
    job_id: str,
    scenario_slug: str,
    scenario_name: str,
    scenario_index: int,
    scenario_count: int,
    planned_modes: list[str],
    page_offset: int,
) -> subprocess.CompletedProcess[str]:
    total_render_count = int(_get_render_job(job_id).get("total_render_count", len(planned_modes))) if _get_render_job(job_id) else len(planned_modes)
    mode_lookup = {mode: index + 1 for index, mode in enumerate(planned_modes)}
    mode_line_re = re.compile(r"Running projection \[(?P<mode>[^\]]+)\]")

    def on_line(line: str) -> None:
        match = mode_line_re.search(line)
        if match:
            mode = str(match.group("mode")).strip().lower()
            mode_index = mode_lookup.get(mode)
            if mode_index is not None:
                completed_render_count = page_offset + mode_index - 1
                _update_render_job(
                    job_id,
                    current_scenario_index=scenario_index,
                    current_scenario_name=scenario_name,
                    current_mode_index=mode_index,
                    current_mode=mode,
                    completed_render_count=completed_render_count,
                    title="Rendering projections",
                    detail=(
                        f"Scenario {scenario_index} of {scenario_count}, "
                        f"mode page {completed_render_count + 1} of "
                        f"{total_render_count}"
                    ),
                    progress=f"{scenario_name} — {mode.replace('_', ' ').title()}",
                )

    result = _render_projection_offline_streaming(scenario_slug, line_callback=on_line)
    _update_render_job(
        job_id,
        current_scenario_index=scenario_index,
        current_scenario_name=scenario_name,
        current_mode_index=len(planned_modes),
        current_mode=planned_modes[-1] if planned_modes else "",
        completed_render_count=page_offset + len(planned_modes),
    )
    return result


def _complete_render_job(
    job_id: str,
    *,
    state: str,
    status_kind: str,
    status_title: str,
    status_message: str,
    details: str | None,
) -> None:
    _update_render_job(
        job_id,
        state=state,
        status_kind=status_kind,
        status_title=status_title,
        status_message=status_message,
        details=details,
        title=status_title,
        detail=status_message,
        progress="Complete." if state == "completed" else "Finished with errors.",
        completed_at=datetime.now().isoformat(),
    )


def _run_render_job_guarded(
    job_id: str,
    worker,
    *args,
) -> None:
    try:
        _update_render_job(
            job_id,
            state="running",
            title="Starting render job",
            progress="Starting background worker…",
        )
        worker(job_id, *args)
    except Exception as exc:
        _complete_render_job(
            job_id,
            state="failed",
            status_kind="error",
            status_title="Render job failed",
            status_message=str(exc),
            details="Background render worker crashed before completion.",
        )


def _start_render_job_thread(job_id: str, worker, *args) -> None:
    threading.Thread(
        target=_run_render_job_guarded,
        args=(job_id, worker, *args),
        daemon=True,
    ).start()


def _run_save_render_job(job_id: str, scenario_slug: str) -> None:
    scenario = _current_scenario(scenario_slug)
    planned_modes = _planned_modes_for_scenario(scenario.slug)
    _update_render_job(
        job_id,
        title="Rendering projections",
        detail=f"Scenario 1 of 1, 0 of {len(planned_modes)} mode pages complete",
        progress="Preparing render process…",
    )
    result = _run_single_scenario_job(
        job_id=job_id,
        scenario_slug=scenario.slug,
        scenario_name=scenario.name,
        scenario_index=1,
        scenario_count=1,
        planned_modes=planned_modes,
        page_offset=0,
    )
    if result.returncode == 0:
        _complete_render_job(
            job_id,
            state="completed",
            status_kind="success",
            status_title="Saved and re-rendered",
            status_message="Configuration saved and offline projection rebuilt successfully.",
            details=(result.stdout or "").strip() or None,
        )
        return
    details = "\n".join(part for part in [(result.stdout or "").strip(), (result.stderr or "").strip()] if part).strip()
    _complete_render_job(
        job_id,
        state="failed",
        status_kind="error",
        status_title="Render failed after save",
        status_message="The config was saved, but the offline projection rebuild failed.",
        details=details or "No process output captured.",
    )


def _run_save_render_all_job(job_id: str, current_scenario_slug: str) -> None:
    scenarios = discover_scenarios()
    total_render_count = sum(len(_planned_modes_for_scenario(scenario.slug)) for scenario in scenarios)
    _update_render_job(
        job_id,
        scenario_count=len(scenarios),
        total_render_count=total_render_count,
        title="Rendering all scenarios",
        detail=f"0 of {total_render_count} mode pages complete",
        progress="Preparing batch render process…",
    )
    results: list[tuple[str, subprocess.CompletedProcess[str]]] = []
    page_offset = 0
    for scenario_index, scenario in enumerate(scenarios, start=1):
        planned_modes = _planned_modes_for_scenario(scenario.slug)
        result = _run_single_scenario_job(
            job_id=job_id,
            scenario_slug=scenario.slug,
            scenario_name=scenario.name,
            scenario_index=scenario_index,
            scenario_count=len(scenarios),
            planned_modes=planned_modes,
            page_offset=page_offset,
        )
        results.append((scenario.slug, result))
        page_offset += len(planned_modes)

    failures = [(slug, result) for slug, result in results if result.returncode != 0]
    # Build failed_scenarios metadata (slug, name, error excerpt)
    scenario_lookup = {s.slug: s.name for s in scenarios}
    failed_scenarios = []
    for slug, result in failures:
        error_text = (result.stderr or "").strip()
        if not error_text:
            error_text = (result.stdout or "").strip()
        failed_scenarios.append({
            "slug": slug,
            "name": scenario_lookup.get(slug, slug),
            "error": error_text or "(no output captured)",
        })
    _update_render_job(job_id, scenario_slug=current_scenario_slug, failed_scenarios=failed_scenarios)

    # Build details string — only failed scenarios, labeled by slug
    details_lines: list[str] = []
    for slug, result in failures:
        label = scenario_lookup.get(slug, slug)
        details_lines.append(f"── {label} [{slug}] ──")
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        if stderr:
            details_lines.append(stderr)
        elif stdout:
            details_lines.append(stdout)
        else:
            details_lines.append("(no output captured)")

    failed_names = ", ".join(f["name"] for f in failed_scenarios)
    _complete_render_job(
        job_id,
        state="failed" if failures else "completed",
        status_kind="error" if failures else "success",
        status_title="Render all completed with errors" if failures else "Render all complete",
        status_message=(
            f"Rendered {len(results)} scenario(s), {len(failures)} failed: {failed_names}"
            if failures
            else f"Rendered {len(results)} scenario(s) successfully."
        ),
        details="\n\n".join(details_lines),
    )


async def _parse_form(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def _start_render_job_response(
    *,
    action: str,
    scenario_slug: str | None,
    backup_path: Path,
) -> JSONResponse:
    scenario = _current_scenario(scenario_slug)
    if action == "save_render":
        planned_modes = _planned_modes_for_scenario(scenario.slug)
        job = _create_render_job(
            action=action,
            scenario_slug=scenario.slug,
            scenario_count=1,
            total_render_count=len(planned_modes),
            backup_path=str(backup_path),
        )
        _start_render_job_thread(job["id"], _run_save_render_job, scenario.slug)
        return JSONResponse(_job_status_payload(_get_render_job(job["id"]) or job))

    if action == "save_render_all":
        scenarios = discover_scenarios()
        total_render_count = sum(len(_planned_modes_for_scenario(item.slug)) for item in scenarios)
        job = _create_render_job(
            action=action,
            scenario_slug=scenario.slug,
            scenario_count=len(scenarios),
            total_render_count=total_render_count,
            backup_path=str(backup_path),
        )
        _start_render_job_thread(job["id"], _run_save_render_all_job, scenario.slug)
        return JSONResponse(_job_status_payload(_get_render_job(job["id"]) or job))

    return JSONResponse({"ok": False, "error": f"Unsupported render action: {action}"}, status_code=400)


_SCENARIOS_MISSING_HELP = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Net Worth Navigator — Getting Started</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; justify-content: center; padding: 2rem; min-height: 100vh; }}
  .card {{ max-width: 640px; width: 100%; background: #1e293b; border-radius: 12px; padding: 2rem; box-shadow: 0 4px 24px rgba(0,0,0,0.3); }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; color: #f8fafc; }}
  p {{ margin-bottom: 1rem; line-height: 1.6; color: #94a3b8; }}
  code {{ background: #334155; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #e2e8f0; }}
  .steps {{ list-style: none; padding: 0; margin: 1.5rem 0; }}
  .steps li {{ padding: 0.75rem 0; border-bottom: 1px solid #334155; line-height: 1.5; }}
  .steps li:last-child {{ border-bottom: none; }}
  .steps li strong {{ color: #f8fafc; }}
  .badge {{ display: inline-block; background: #3b82f6; color: #fff; border-radius: 50%; width: 24px; height: 24px; text-align: center; line-height: 24px; font-size: 0.8rem; font-weight: 700; margin-right: 8px; flex-shrink: 0; }}
  .tip {{ background: #1e3a5f; border-left: 3px solid #3b82f6; padding: 0.75rem 1rem; border-radius: 0 6px 6px 0; margin: 1rem 0; font-size: 0.9rem; }}
  hr {{ border: none; border-top: 1px solid #334155; margin: 1.5rem 0; }}
</style>
</head>
<body>
<div class="card">
  <h1>📋 Net Worth Navigator</h1>
  <p>Welcome! The <code>scenarios/</code> directory is empty — no scenario configs were found.</p>
  <p>To get started, choose one of these options:</p>
  <ul class="steps">
    <li><span class="badge">1</span> <strong>Start from the blank template</strong><br>Copy <code>scenarios/starter.toml</code> to <code>scenarios/default.toml</code> and fill in your details.</li>
    <li><span class="badge">2</span> <strong>Explore the sample scenario</strong><br>Run <code>python run.py --scenario sample</code> to see the app working with example data (Alex &amp; Sam).</li>
    <li><span class="badge">3</span> <strong>No Monarch?</strong><br>Set <code>[data_source].mode = "synthetic"</code> in your scenario and enter balances manually via the Setup Panel.</li>
  </ul>
  <div class="tip">
    💡 <strong>Quick start:</strong><br>
    <code>cp scenarios/starter.toml scenarios/default.toml</code><br>
    Then reload this page and use the Setup Panel to configure your household.
  </div>
  <hr>
  <p style="font-size:0.85rem;color:#64748b;">
    Sample scenarios are pre-configured and available at
    <a href="/finances/projection.html" style="color:#60a5fa;">the projection page</a>.
  </p>
</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def editor_home(request: Request) -> HTMLResponse:
    """Legacy root route — redirect to the Setup Panel."""
    return HTMLResponse(
        "<!DOCTYPE html><html><head>"
        "<meta http-equiv=\"refresh\" content=\"0;url=/setup\">"
        "</head><body></body></html>",
        status_code=302,
        headers={"Location": "/setup"},
    )


@app.get("/setup", response_class=HTMLResponse)
@app.get("/finances/config/setup", response_class=HTMLResponse)
async def setup_panel(request: Request, response: Response) -> HTMLResponse:
    scenario_slug = request.query_params.get("scenario")
    try:
        content = _read_config_text(scenario_slug)
    except (FileNotFoundError, KeyError):
        return HTMLResponse(_SCENARIOS_MISSING_HELP, status_code=200)
    context = _build_context(
        request,
        content=content,
        scenario_slug=scenario_slug,
        status_kind="info",
        status_title="Scenario Setup",
        status_message="Configure scenario parameters, data sources, and starting balances.",
        clone_name="",
        clone_slug="",
        clone_description="",
    )
    tmpl = templates.TemplateResponse(request, "setup_panel.html", context)
    tmpl.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    tmpl.headers["Pragma"] = "no-cache"
    tmpl.headers["Expires"] = "0"
    return tmpl


@app.get("/definitions", response_class=HTMLResponse)
@app.get("/finances/config/definitions", response_class=HTMLResponse)
async def definitions_page() -> HTMLResponse:
    return HTMLResponse(
        build_definitions_page_html(
            editor_url="/finances/config/",
            projection_url="/finances/projection.html",
        )
    )


@app.post("/", response_class=HTMLResponse)
async def editor_submit(request: Request) -> HTMLResponse:
    form = await _parse_form(request)
    action = form.get("action", "validate")
    content = form.get("content", "")
    scenario_slug = form.get("scenario_slug") or None
    clone_name = form.get("clone_name", "")
    clone_slug = form.get("clone_slug", "")
    clone_description = form.get("clone_description", "")
    wants_json = (
        request.headers.get("x-requested-with", "").lower() == "fetch"
        or str(form.get("_response_format", "")).strip().lower() == "json"
    )

    try:
        parsed = _validate_config_text(content)
        summary = (
            f"Valid TOML. Sections: {', '.join(parsed.keys())}."
            if isinstance(parsed, dict) and parsed
            else "Valid TOML."
        )

        if action == "validate":
            context = _build_context(
                request,
                content=content,
                status_kind="success",
                status_title="Validation passed",
                status_message=summary,
                scenario_slug=scenario_slug,
                last_action=action,
                clone_name=clone_name,
                clone_slug=clone_slug,
                clone_description=clone_description,
            )
            return templates.TemplateResponse(request, "config_editor.html", context)

        if action == "clone":
            created = create_scenario_from_content(
                content,
                name=clone_name,
                slug=clone_slug,
                description=clone_description,
            )
            cloned_content = _read_config_text(created.slug)
            context = _build_context(
                request,
                content=cloned_content,
                status_kind="success",
                status_title="Scenario cloned",
                status_message=f"Created scenario '{created.name}' ({created.slug}). Render it via Save + Re-render when ready.",
                scenario_slug=created.slug,
                last_action=action,
                clone_name="",
                clone_slug="",
                clone_description="",
            )
            return templates.TemplateResponse(request, "config_editor.html", context)

        backup_path = _backup_and_write(content, scenario_slug)

        if action == "save":
            context = _build_context(
                request,
                content=content,
                status_kind="success",
                status_title="Saved",
                status_message="Configuration saved successfully.",
                backup_path=str(backup_path),
                scenario_slug=scenario_slug,
                last_action=action,
                clone_name=clone_name,
                clone_slug=clone_slug,
                clone_description=clone_description,
            )
            return templates.TemplateResponse(request, "config_editor.html", context)

        if action == "save_render":
            if wants_json:
                return _start_render_job_response(
                    action=action,
                    scenario_slug=scenario_slug,
                    backup_path=backup_path,
                )
            result = _render_projection_offline(scenario_slug)
            if result.returncode == 0:
                details = (result.stdout or "").strip()
                context = _build_context(
                    request,
                    content=content,
                    status_kind="success",
                    status_title="Saved and re-rendered",
                    status_message="Configuration saved and offline projection rebuilt successfully.",
                    details=details,
                    backup_path=str(backup_path),
                    scenario_slug=scenario_slug,
                    last_action=action,
                    clone_name=clone_name,
                    clone_slug=clone_slug,
                    clone_description=clone_description,
                )
                return templates.TemplateResponse(request, "config_editor.html", context)

            details = "\n".join(part for part in [(result.stdout or "").strip(), (result.stderr or "").strip()] if part).strip()
            context = _build_context(
                request,
                content=content,
                status_kind="error",
                status_title="Render failed after save",
                status_message="The config was saved, but the offline projection rebuild failed.",
                details=details or "No process output captured.",
                backup_path=str(backup_path),
                scenario_slug=scenario_slug,
                last_action=action,
                clone_name=clone_name,
                clone_slug=clone_slug,
                clone_description=clone_description,
            )
            return templates.TemplateResponse(request, "config_editor.html", context, status_code=500)

        if action == "save_render_all":
            if wants_json:
                return _start_render_job_response(
                    action=action,
                    scenario_slug=scenario_slug,
                    backup_path=backup_path,
                )
            results = _render_all_scenarios()
            failures = [
                (slug, result) for slug, result in results if result.returncode != 0
            ]
            details_lines = []
            for slug, result in results:
                details_lines.append(f"[{slug}] exit={result.returncode}")
                stdout = (result.stdout or "").strip()
                stderr = (result.stderr or "").strip()
                if stdout:
                    details_lines.append(stdout)
                if stderr:
                    details_lines.append(stderr)
            context = _build_context(
                request,
                content=content,
                status_kind="error" if failures else "success",
                status_title="Render all complete" if not failures else "Render all completed with errors",
                status_message=(
                    f"Saved current scenario and rendered {len(results)} scenario(s) successfully."
                    if not failures
                    else f"Saved current scenario and rendered {len(results)} scenario(s), with {len(failures)} failure(s)."
                ),
                details="\n\n".join(details_lines),
                backup_path=str(backup_path),
                scenario_slug=scenario_slug,
                last_action=action,
                clone_name=clone_name,
                clone_slug=clone_slug,
                clone_description=clone_description,
            )
            return templates.TemplateResponse(
                request,
                "config_editor.html",
                context,
                status_code=500 if failures else 200,
            )

        context = _build_context(
            request,
            content=content,
            status_kind="error",
            status_title="Unknown action",
            status_message=f"Unsupported action: {html.escape(action)}",
            scenario_slug=scenario_slug,
            last_action=action,
            clone_name=clone_name,
            clone_slug=clone_slug,
            clone_description=clone_description,
        )
        return templates.TemplateResponse(request, "config_editor.html", context, status_code=400)

    except tomllib.TOMLDecodeError as exc:
        context = _build_context(
            request,
            content=content,
            status_kind="error",
            status_title="Validation failed",
            status_message=str(exc),
            scenario_slug=scenario_slug,
            last_action=action,
            clone_name=clone_name,
            clone_slug=clone_slug,
            clone_description=clone_description,
        )
        return templates.TemplateResponse(request, "config_editor.html", context, status_code=400)
    except Exception as exc:
        context = _build_context(
            request,
            content=content,
            status_kind="error",
            status_title="Operation failed",
            status_message=str(exc),
            scenario_slug=scenario_slug,
            last_action=action,
            clone_name=clone_name,
            clone_slug=clone_slug,
            clone_description=clone_description,
        )
        return templates.TemplateResponse(request, "config_editor.html", context, status_code=500)


@app.get("/health")
async def health() -> JSONResponse:
    scenario = _current_scenario()
    return JSONResponse({
        "ok": True,
        "config_path": str(_config_path(scenario.slug)),
        "scenario_slug": scenario.slug,
        "projection_url": f"{PUBLIC_PROJECTION_URL}?scenario={scenario.slug}",
        "editor_url": f"{PUBLIC_EDITOR_URL}?scenario={scenario.slug}",
    })


@app.post("/rename-scenario")
@app.post("/finances/config/rename-scenario")
async def rename_scenario(request: Request) -> JSONResponse:
    """Rename a non-default scenario: rewrite its [scenario] block, move the file."""
    from src.scenarios import materialize_scenario_content, scenario_path_for_slug

    form = await _parse_form(request)
    scenario_slug = (form.get("scenario_slug") or "").strip()
    new_name = (form.get("new_name") or "").strip()
    new_slug = (form.get("new_slug") or "").strip()
    new_description = (form.get("new_description") or "").strip()

    if not new_name or not new_slug:
        return JSONResponse({"ok": False, "error": "New name and slug are required."}, status_code=400)

    try:
        scenario = _current_scenario(scenario_slug)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Scenario not found: {exc}"}, status_code=404)

    if scenario.is_default:
        return JSONResponse({"ok": False, "error": "The default scenario cannot be renamed."}, status_code=400)

    new_path = scenario_path_for_slug(new_slug)
    if new_path.exists() and new_path != scenario.config_path:
        return JSONResponse({"ok": False, "error": f"A scenario with slug '{new_slug}' already exists."}, status_code=409)

    source_content = scenario.config_path.read_text(encoding="utf-8")
    new_content = materialize_scenario_content(
        source_content,
        name=new_name,
        slug=new_slug,
        description=new_description or scenario.description,
        is_default=False,
    )

    # Write new file, remove old if slug changed
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(new_content, encoding="utf-8")
    if new_path != scenario.config_path:
        scenario.config_path.unlink(missing_ok=True)

    # Trigger offline render of the renamed scenario to update the manifest
    try:
        _render_projection_offline(new_slug)
    except Exception:
        pass

    return JSONResponse({
        "ok": True,
        "old_slug": scenario_slug,
        "new_slug": new_slug,
        "new_name": new_name,
        "message": f"Scenario renamed to '{new_name}' ({new_slug}).",
        "redirect_url": f"{PUBLIC_EDITOR_URL}?scenario={new_slug}",
    })


@app.post("/delete-scenario")
@app.post("/finances/config/delete-scenario")
async def delete_scenario(request: Request) -> JSONResponse:
    import shutil

    form = await _parse_form(request)
    scenario_slug = (form.get("scenario_slug") or "").strip()
    confirm = (form.get("confirm") or "").strip()

    if confirm != scenario_slug:
        return JSONResponse(
            {"ok": False, "error": "Confirmation slug did not match. Scenario not deleted."},
            status_code=400,
        )

    try:
        scenario = _current_scenario(scenario_slug)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Scenario not found: {exc}"}, status_code=404)

    if scenario.is_default:
        return JSONResponse(
            {"ok": False, "error": "The default scenario cannot be deleted."},
            status_code=400,
        )

    # Remove the TOML config file
    config_path = scenario.config_path
    if config_path.exists():
        config_path.unlink()

    # Remove rendered output directory (non-fatal if missing)
    scenario_output_dir = OUTPUT_DIR / "scenarios" / scenario_slug
    if scenario_output_dir.exists():
        shutil.rmtree(scenario_output_dir, ignore_errors=True)

    # Remove deployed output directory (non-fatal if missing)
    deploy_scenario_dir = APP_ROOT / "output" / "scenarios" / scenario_slug
    if deploy_scenario_dir != scenario_output_dir and deploy_scenario_dir.exists():
        shutil.rmtree(deploy_scenario_dir, ignore_errors=True)

    # Rebuild the shell + compare pages so the deleted scenario disappears from selectors
    # (lightweight — just rewrites manifest + HTML, no re-projection)
    try:
        from src.definitions_page import build_definitions_page_html
        # Rebuild scenario index (discovers only surviving scenario files)
        ts = datetime.now().isoformat()
        write_scenarios_index(output_root=OUTPUT_DIR / "scenarios", cache_timestamp=None)
        # Re-read the updated index
        index_path = OUTPUT_DIR / "scenarios" / "index.json"
        with open(index_path) as fh:
            manifest = json.load(fh)
        # Rebuild shell pages
        build_scenario_shell(
            manifest=manifest,
            output_path=OUTPUT_DIR / "projection.html",
        )
        build_compare_page(
            manifest=manifest,
            output_path=OUTPUT_DIR / "compare.html",
        )
        # Rebuild definitions page
        defs_html = build_definitions_page_html(
            editor_url="/finances/config/",
            projection_url="/finances/projection.html",
        )
        (OUTPUT_DIR / "definitions.html").write_text(defs_html, encoding="utf-8")
    except Exception:
        pass  # non-fatal; shell pages will be stale until next render

    return JSONResponse({
        "ok": True,
        "deleted_slug": scenario_slug,
        "message": f"Scenario '{scenario.name}' ({scenario_slug}) deleted.",
    })


@app.get("/jobs/{job_id}")
@app.get("/finances/config/jobs/{job_id}")
async def render_job_status(job_id: str) -> JSONResponse:
    job = _get_render_job(job_id)
    if job is None:
        return JSONResponse({"ok": False, "error": "Job not found."}, status_code=404)
    return JSONResponse({"ok": True, **_job_status_payload(job)})


@app.post("/render-jobs")
@app.post("/finances/config/render-jobs")
async def start_render_job(request: Request) -> JSONResponse:
    form = await _parse_form(request)
    action = form.get("action", "")
    content = form.get("content", "")
    scenario_slug = form.get("scenario_slug") or None

    if action not in {"save_render", "save_render_all"}:
        return JSONResponse({"ok": False, "error": f"Unsupported render action: {action}"}, status_code=400)

    try:
        _validate_config_text(content)
        backup_path = _backup_and_write(content, scenario_slug)
        return _start_render_job_response(
            action=action,
            scenario_slug=scenario_slug,
            backup_path=backup_path,
        )
    except tomllib.TOMLDecodeError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── tomlkit helpers ──────────────────────────────────────────────────────────

def _toml_open(scenario_slug: str | None = None) -> tuple[tomlkit.TOMLDocument, Path]:
    path = _config_path(scenario_slug)
    return tomlkit.parse(path.read_text(encoding="utf-8")), path


def _backup_and_write_toml(doc: tomlkit.TOMLDocument, scenario_slug: str | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    backup_dir = _backup_dir(scenario_slug)
    backup_dir.mkdir(parents=True, exist_ok=True)

    config_path = _config_path(scenario_slug)
    current_content = config_path.read_text(encoding="utf-8")

    # Deduplicate: skip creating a new backup if the last backup matches current state
    last_content = _last_backup_content(backup_dir)
    if last_content is not None and last_content == current_content:
        backups = sorted(
            backup_dir.glob("config-*.toml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        backup_path = backups[0]
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"config-{ts}.toml"
        backup_path.write_text(current_content, encoding="utf-8")

    config_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    # fsync to flush the write through any bind-mount / Docker storage delay
    # so the file is immediately visible from the host side.
    fd = os.open(str(config_path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    _prune_backups(backup_dir)
    return backup_path


def _cache_path() -> Path:
    return OUTPUT_DIR / "balances_cache.json"


def _load_cached_raw_accounts() -> tuple[list[dict], str | None]:
    cache_p = _cache_path()
    if not cache_p.exists():
        return [], None
    try:
        data = json.loads(cache_p.read_text())
        raw = data.get("raw_accounts", [])
        ts = data.get("timestamp")
        return raw, ts
    except Exception:
        return [], None


def _tombstone_accounts_section(doc: tomlkit.TOMLDocument) -> None:
    """Remove all account-name keys from [accounts], keep the section itself."""
    accounts = doc.get("accounts")
    if accounts is None or not isinstance(accounts, dict):
        return
    keys_to_remove = [k for k in accounts if k != "disabled"]
    for k in keys_to_remove:
        accounts.remove(k)  # tomlkit dicts have .remove()


def _classify_raw_accounts(
    raw: list[dict], config: dict | None = None,
) -> dict[str, str | dict]:
    """Build a name→category map from the current config."""
    if config is None:
        config = {}
    raw_map: dict = config.get("accounts", {})
    return {acct["name"]: raw_map.get(acct["name"], "unclassified") for acct in raw}


# ── API: new scenario from starter template ─────────────────────────────────

@app.post("/api/new-scenario")
async def api_new_scenario(request: Request) -> JSONResponse:
    """Create a new scenario by copying a starter template and rewriting its metadata."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body."}, status_code=400)

    name = str(body.get("name", "")).strip()
    slug = str(body.get("slug", "")).strip()
    description = str(body.get("description", "")).strip()
    household_type = str(body.get("household_type", "single")).strip().lower()

    if not name:
        return JSONResponse({"ok": False, "error": "Scenario name is required."}, status_code=400)
    if not slug:
        return JSONResponse({"ok": False, "error": "Scenario slug is required."}, status_code=400)

    # Choose the starter template based on household type
    template_name = "starter-couple" if household_type == "couple" else "starter"
    starter_path = SCENARIOS_DIR / f"{template_name}.toml"
    if not starter_path.exists():
        # Fallback: use the minimal required TOML inline if no template is found
        source_content = (
            '[scenario]\nname = ""\nslug = ""\ndescription = ""\nis_default = false\n\n'
            '[data_source]\nmode = "synthetic"\n\n[synthetic_start]\ntaxable = 0\n'
            'trad_ira = 0\nroth = 0\ncash = 0\nhome_value = 0\nvehicles = 0\nother = 0\n'
        )
    else:
        source_content = starter_path.read_text(encoding="utf-8")

    try:
        ref = create_scenario_from_content(
            source_content,
            name=name,
            slug=slug,
            description=description or f"Created from starter template.",
        )
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Failed to create scenario: {exc}"}, status_code=500)

    return JSONResponse({"ok": True, "slug": ref.slug, "name": ref.name})


# ── API: data-source status ─────────────────────────────────────────────────

@app.get("/api/data-source-status")
async def api_data_source_status(request: Request) -> JSONResponse:
    scenario_slug = request.query_params.get("scenario") or None
    raw_accounts, cache_ts = _load_cached_raw_accounts()
    cache_age_days: float | None = None
    if cache_ts:
        try:
            parsed_ts = datetime.fromisoformat(cache_ts)
            cache_age_days = (datetime.now() - parsed_ts).total_seconds() / 86400
        except Exception:
            pass

    config_text = _read_config_text(scenario_slug)
    parsed = tomllib.loads(config_text)
    data_source_mode = "monarch"
    if isinstance(parsed.get("data_source"), dict):
        data_source_mode = parsed["data_source"].get("mode") or "monarch"

    status_per_account: dict = {}
    for acct in raw_accounts:
        name = acct["name"]
        status_per_account[name] = {
            "source": data_source_mode,
            "cache_age_days": cache_age_days,
        }

    return JSONResponse({
        "ok": True,
        "mode": data_source_mode,
        "cache_timestamp": cache_ts,
        "cache_age_days": cache_age_days,
        "accounts": status_per_account,
        "total_accounts": len(raw_accounts),
    })


# ── API: refresh monarch ────────────────────────────────────────────────────

@app.post("/api/refresh-monarch")
async def api_refresh_monarch() -> JSONResponse:
    from src.monarch_bridge import MCP_PYTHON, fetch_raw_accounts, classify_accounts, load_config as monarch_config

    if not MCP_PYTHON.exists():
        return JSONResponse(
            {
                "ok": False,
                "error": (
                    "Monarch MCP server is not installed on this system. "
                    "Switch to Manual Entry (synthetic) mode instead, or install and "
                    "configure the Monarch MCP server. "
                    f"(Checked: {MCP_PYTHON}; "
                    "set the MONARCH_MCP_PATH environment variable to your MCP "
                    "server's root directory to use a custom location.)"
                ),
            },
            status_code=503,
        )

    try:
        raw = fetch_raw_accounts()
        config = monarch_config()
        portfolio, extras = classify_accounts(raw, config)

        OUTPUT_DIR.mkdir(exist_ok=True)
        now = datetime.now().isoformat()
        cache_path = _cache_path()
        cache_path.write_text(
            json.dumps({
                "timestamp": now,
                "raw_accounts": raw,
                "portfolio": portfolio,
                "extras": extras,
            }, indent=2),
        )

        return JSONResponse({
            "ok": True,
            "accounts": raw,
            "cache_timestamp": now,
            "source": "live",
            "account_count": len(raw),
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Monarch refresh failed: {exc}"}, status_code=502)


# ── API: accounts (cached) ──────────────────────────────────────────────────

@app.get("/api/accounts")
async def api_accounts(request: Request) -> JSONResponse:
    scenario_slug = request.query_params.get("scenario") or None
    raw_accounts, cache_ts = _load_cached_raw_accounts()
    source = "cached" if cache_ts else "none"

    config_text = _read_config_text(scenario_slug)
    parsed = tomllib.loads(config_text)
    accounts_section = parsed.get("accounts", {})
    disabled: list[str] = []
    classification: dict[str, str | dict] = {}
    if isinstance(accounts_section, dict):
        disabled = list(accounts_section.get("disabled", []))
        for key, value in accounts_section.items():
            if key == "disabled":
                continue
            classification[str(key)] = value

    source_mode = "monarch"
    if isinstance(parsed.get("data_source"), dict):
        source_mode = parsed["data_source"].get("mode") or "monarch"

    if source_mode == "csv_import":
        # Return CSV source accounts, not Monarch cache
        csv_source = parsed.get("csv_source", {}) or {}
        csv_accounts = csv_source.get("accounts", {}) or {}
        if not isinstance(csv_accounts, dict):
            csv_accounts = {}
        csv_list = [{"name": name, "balance": bal} for name, bal in sorted(csv_accounts.items())]
        return JSONResponse({
            "ok": True,
            "accounts": csv_list,
            "cache_timestamp": None,
            "source": "csv",
            "source_mode": "csv_import",
            "classification": classification,
            "disabled": disabled,
            "account_count": len(csv_list),
        })

    if source_mode == "synthetic":
        # No account-level data — return empty.  If the user has CSV source
        # accounts (switched radio but not yet saved), surface those.
        csv_source = parsed.get("csv_source", {}) or {}
        csv_accounts = csv_source.get("accounts", {}) or {}
        if isinstance(csv_accounts, dict) and csv_accounts:
            csv_list = [{"name": name, "balance": bal} for name, bal in sorted(csv_accounts.items())]
            return JSONResponse({
                "ok": True,
                "accounts": csv_list,
                "cache_timestamp": None,
                "source": "csv",
                "source_mode": "csv_import",
                "classification": classification,
                "disabled": disabled,
                "account_count": len(csv_list),
            })
        return JSONResponse({
            "ok": True,
            "accounts": [],
            "cache_timestamp": None,
            "source": "synthetic",
            "source_mode": "synthetic",
            "classification": classification,
            "disabled": disabled,
            "account_count": 0,
        })

    return JSONResponse({
        "ok": True,
        "accounts": raw_accounts,
        "cache_timestamp": cache_ts,
        "source": source,
        "source_mode": source_mode,
        "classification": classification,
        "disabled": disabled,
        "account_count": len(raw_accounts),
    })


# ── API: save classification ────────────────────────────────────────────────

@app.post("/api/save-classification")
async def api_save_classification(request: Request) -> JSONResponse:
    scenario_slug = request.query_params.get("scenario") or None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Request body must be JSON."}, status_code=400)

    entries: list[dict] | None = body.get("accounts")
    if entries is None:
        return JSONResponse({"ok": False, "error": "Missing 'accounts' list."}, status_code=400)

    disabled_names: list[str] = [e["name"] for e in entries if e.get("disabled")]
    active = [e for e in entries if not e.get("disabled")]

    doc, _ = _toml_open(scenario_slug)
    accounts = doc.get("accounts")
    if accounts is None or not isinstance(accounts, dict):
        # create a new table if none exists
        doc["accounts"] = {}
        accounts = doc["accounts"]

    # Remove old account-name keys, keep disabled key
    _tombstone_accounts_section(doc)

    # Set disabled list
    accounts["disabled"] = disabled_names

    # Add each active account classification
    for entry in active:
        name: str = entry["name"]
        category: str = entry.get("category", "ignore")
        owner: str = entry.get("owner", "n/a")
        if owner and owner != "n/a":
            # Write inline dict with owner metadata
            accounts[name] = {"category": category, "owner": owner}
        else:
            accounts[name] = category

    backup_path = _backup_and_write_toml(doc, scenario_slug)
    return JSONResponse({
        "ok": True,
        "message": f"Classification saved for {len(entries)} account(s).",
        "backup_path": str(backup_path),
        "toml_content": doc.as_string(),
    })


# ── API: synthetic-start GET ────────────────────────────────────────────────

@app.get("/api/synthetic-start")
async def api_synthetic_start(request: Request) -> JSONResponse:
    scenario_slug = request.query_params.get("scenario") or None
    config_text = _read_config_text(scenario_slug)
    parsed = tomllib.loads(config_text)
    synthetic = parsed.get("synthetic_start", {})
    if not isinstance(synthetic, dict):
        synthetic = {}

    data_source = parsed.get("data_source", {})
    mode = "monarch"
    if isinstance(data_source, dict):
        mode = data_source.get("mode", "monarch")

    defaults = {"taxable": 0, "trad_ira": 0, "roth": 0, "cash": 0,
                 "taxable_cost_basis": 0, "roth_contribution_basis": 0,
                 "home_value": 0, "vehicles": 0}
    for key in defaults:
        if key not in synthetic:
            synthetic[key] = defaults[key]

    if "liability_balances" not in synthetic or not isinstance(synthetic.get("liability_balances"), dict):
        synthetic["liability_balances"] = {}
    if "property_values" not in synthetic or not isinstance(synthetic.get("property_values"), dict):
        synthetic["property_values"] = {}

    # Read liabilities list from config for auto-detected field names
    liabilities_list = parsed.get("liabilities", [])
    if isinstance(liabilities_list, list):
        synthetic["_liability_names"] = [item.get("name", "") for item in liabilities_list if isinstance(item, dict)]

    return JSONResponse({
        "ok": True,
        "data_source_mode": mode,
        "synthetic_start": synthetic,
    })


# ── API: save synthetic-start ───────────────────────────────────────────────

@app.post("/api/save-synthetic-start")
async def api_save_synthetic_start(request: Request) -> JSONResponse:
    scenario_slug = request.query_params.get("scenario") or None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Request body must be JSON."}, status_code=400)

    data_source: str = body.get("data_source", "monarch")
    balances: dict = body.get("balances", {})

    if data_source == "synthetic":
        # Require at least some balances
        total = sum(
            float(v) for v in balances.values()
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip())
        )
        if total <= 0:
            # Check nested dicts too
            nested_total = 0
            for v in balances.values():
                if isinstance(v, dict):
                    nested_total += sum(float(sv) for sv in v.values() if isinstance(sv, (int, float)))
            if total + nested_total <= 0:
                return JSONResponse({
                    "ok": False,
                    "error": "Synthetic mode requires at least one non-zero starting balance.",
                }, status_code=400)

    # Separate out structured sub-maps
    liability_balances: dict = {}
    property_values: dict = {}
    clean_balances: dict = {}
    for key, value in balances.items():
        if isinstance(value, dict):
            if key == "liability_balances":
                liability_balances = {k: float(v) for k, v in value.items() if isinstance(v, (int, float, str)) and str(v).strip()}
            elif key == "property_values":
                property_values = {k: float(v) for k, v in value.items() if isinstance(v, (int, float, str)) and str(v).strip()}
            continue
        clean_balances[key] = float(value) if isinstance(value, (int, float)) else 0

    doc, _ = _toml_open(scenario_slug)

    # Set data_source.mode
    if "data_source" not in doc or doc["data_source"] is None:
        doc["data_source"] = tomlkit.table()
    doc["data_source"]["mode"] = data_source

    # Set synthetic_start
    if clean_balances or liability_balances or property_values:
        syn = tomlkit.table()
        for k, v in clean_balances.items():
            if v != 0:
                syn[k] = v
        if liability_balances:
            syn["liability_balances"] = liability_balances
        if property_values:
            syn["property_values"] = property_values
        doc["synthetic_start"] = syn
    else:
        # Clear the section
        doc.pop("synthetic_start", None)

    backup_path = _backup_and_write_toml(doc, scenario_slug)
    return JSONResponse({
        "ok": True,
        "message": f"Data source set to '{data_source}' and synthetic balances saved.",
        "backup_path": str(backup_path),
        "toml_content": doc.as_string(),
    })


# ── API: save quick controls ────────────────────────────────────────────────

_QUICK_CONTROL_MAP: dict[str, tuple[str, type]] = {
    "cash_target_accumulation": ("withdrawal_policy.accumulation_cash_target", float),
    "cash_target_retirement": ("withdrawal_policy.retirement_cash_target", float),
    "cash_target_survivor": ("withdrawal_policy.survivor_cash_target", float),
    "stock_return": ("assumptions.stock_return", float),
    "bond_return": ("assumptions.bond_return", float),
    "person1_retirement_year": ("person1.retirement_year", int),
    "person2_retirement_year": ("person2.retirement_year", int),
    "person1_name": ("person1.name", str),
    "person2_name": ("person2.name", str),
    "inflation": ("assumptions.inflation", float),
    "equity_allocation": ("assumptions.equity_allocation", float),
    "simulation_start_year": ("simulation.start_year", int),
    "simulation_end_year": ("simulation.end_year", int),
    "scenario_name": ("scenario.name", str),
    "scenario_description": ("scenario.description", str),
    "household_type": ("scenario.household_type", str),
    "table_set": ("taxes.table_set", str),
}

_QUICK_ARRAY_MAP: dict[str, str] = {
    "retirement_withdrawal_order": "withdrawal_policy.retirement_withdrawal_order",
    "accumulation_withdrawal_order": "withdrawal_policy.accumulation_withdrawal_order",
    "survivor_withdrawal_order": "withdrawal_policy.survivor_withdrawal_order",
    "retirement_surplus_order": "withdrawal_policy.retirement_surplus_order",
    "accumulation_surplus_order": "withdrawal_policy.accumulation_surplus_order",
    "survivor_surplus_order": "withdrawal_policy.survivor_surplus_order",
}


def _resolve_toml_path(doc: tomlkit.TOMLDocument, dotted: str) -> tuple:
    """Walk a dotted path like 'assumptions.stock_return' and return (parent, key)."""
    parts = dotted.split(".")
    current = doc
    for part in parts[:-1]:
        if part not in current or current[part] is None:
            current[part] = tomlkit.table()
        current = current[part]
    return current, parts[-1]


@app.post("/api/save-quick-controls")
async def api_save_quick_controls(request: Request) -> JSONResponse:
    scenario_slug = request.query_params.get("scenario") or None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Request body must be JSON."}, status_code=400)

    doc, _ = _toml_open(scenario_slug)
    
    # If the client included the raw TOML textarea content, use that as the
    # base document instead of re-reading the file.  This preserves any raw
    # edits the user made (e.g. uncommenting real_dollar_basis) that would
    # otherwise be lost when the file is re-read and overwritten.
    raw_content = body.get("_raw_toml_content")
    if raw_content and isinstance(raw_content, str) and raw_content.strip():
        doc = tomlkit.parse(raw_content)
    
    changed_keys: list[str] = []

    def _value_differs(parent: dict, key: str, typed) -> bool:
        """Compare new value against existing. Treat str ↔ int/float as equal if numeric."""
        existing = parent.get(key)
        if existing is None:
            return True
        if type(existing) == type(typed):
            return existing != typed
        # Allow cross-type comparison: "1980" == 1980
        try:
            return float(existing) != float(typed)
        except (TypeError, ValueError):
            return str(existing) != str(typed)

    # Scalar fields
    for field_name, (toml_path, value_type) in _QUICK_CONTROL_MAP.items():
        raw = body.get(field_name)
        if raw is None:
            continue
        try:
            typed = value_type(raw) if not isinstance(raw, str) or isinstance(raw, bool) else value_type(raw)
        except (TypeError, ValueError):
            continue
        parent, key = _resolve_toml_path(doc, toml_path)
        if _value_differs(parent, key, typed):
            parent[key] = typed
            changed_keys.append(toml_path)

    # Array fields
    for field_name, toml_path in _QUICK_ARRAY_MAP.items():
        raw = body.get(field_name)
        if raw is None or not isinstance(raw, list):
            continue
        parent, key = _resolve_toml_path(doc, toml_path)
        existing = parent.get(key)
        if existing is None or list(existing) != raw:
            parent[key] = raw
            changed_keys.append(toml_path)

    # data_source mode (special case — radio button)
    ds_mode = body.get("data_source")
    if ds_mode in ("monarch", "synthetic", "csv_import"):
        if "data_source" not in doc or doc["data_source"] is None:
            doc["data_source"] = tomlkit.table()
        existing_mode = doc["data_source"].get("mode")
        if existing_mode != ds_mode:
            doc["data_source"]["mode"] = ds_mode
            changed_keys.append("data_source.mode")

    # Birth years (reconstruct dob string from year)
    for person_key, field_name in [("person1", "person1_birth_year"), ("person2", "person2_birth_year")]:
        raw_by = body.get(field_name)
        if raw_by is not None:
            try:
                birth_year = int(raw_by)
            except (TypeError, ValueError):
                continue
            if person_key not in doc or doc[person_key] is None:
                doc[person_key] = tomlkit.table()
            current_dob = str(doc[person_key].get("dob", ""))
            # Preserve existing month/day if present, else default to Jan 1
            if current_dob and "-" in current_dob and len(current_dob.split("-")) == 3:
                month_day = "-".join(current_dob.split("-")[1:])
            else:
                month_day = "01-01"
            new_dob = f"{birth_year}-{month_day}"
            if current_dob != new_dob:
                doc[person_key]["dob"] = new_dob
                changed_keys.append(f"{person_key}.dob")

    if not changed_keys:
        # Check whether any recognized fields were present in the request body at all
        any_recognized = any(
            field in body
            for field in list(_QUICK_CONTROL_MAP.keys())
            + list(_QUICK_ARRAY_MAP.keys())
            + ["data_source", "person1_birth_year", "person2_birth_year", "household_type"]
        )
        if not any_recognized:
            return JSONResponse({"ok": False, "error": "No recognised fields in request."}, status_code=400)
        # Recognized fields were sent but none changed — still a success
        # BUT: if _raw_toml_content was provided, the user's raw edits need
        # to be persisted even though the form fields didn't change.
        if raw_content and isinstance(raw_content, str) and raw_content.strip():
            backup_path = _backup_and_write_toml(doc, scenario_slug)
            return JSONResponse({
                "ok": True,
                "message": "Raw TOML updated.",
                "changed_keys": [],
                "backup_path": str(backup_path),
                "toml_content": doc.as_string(),
            })
        return JSONResponse({
            "ok": True,
            "message": "No changes detected.",
            "changed_keys": [],
            "backup_path": None,
            "toml_content": doc.as_string(),
        })

    backup_path = _backup_and_write_toml(doc, scenario_slug)
    return JSONResponse({
        "ok": True,
        "message": f"Updated {len(changed_keys)} field(s).",
        "changed_keys": changed_keys,
        "backup_path": str(backup_path),
        "toml_content": doc.as_string(),
    })


@app.get("/api/validate-scenario")
async def api_validate_scenario(request: Request) -> JSONResponse:
    """
    Validate the current scenario configuration for common errors.
    Returns validation status and list of issues if any.
    """
    try:
        scenario_slug = request.query_params.get("scenario") or None
        config_path = _config_path(scenario_slug)
        
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
        except Exception as exc:
            return JSONResponse({
                "ok": False,
                "is_valid": False,
                "errors": [f"Failed to load config file: {exc}"]
            }, status_code=400)
        
        from src.model import validate_scenario
        is_valid, validation_errors = validate_scenario(config, config_path)
        
        return JSONResponse({
            "ok": True,
            "is_valid": is_valid,
            "errors": validation_errors,
            "config_path": str(config_path),
        })
    except Exception as exc:
        # Catch any unexpected errors and return JSON instead of HTML error page
        import traceback
        return JSONResponse({
            "ok": False,
            "is_valid": False,
            "errors": [f"Validation error: {str(exc)}", traceback.format_exc()]
        }, status_code=500)


@app.post("/api/set-default-scenario")
async def api_set_default_scenario(request: Request) -> JSONResponse:
    """Set or unset a scenario as the default. Only one scenario can be default at a time."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Request body must be JSON."}, status_code=400)

    slug = (body.get("slug") or "").strip()
    is_default = body.get("is_default", True)
    if not slug:
        return JSONResponse({"ok": False, "error": "slug is required."}, status_code=400)

    try:
        from src.scenarios import discover_scenarios

        if is_default:
            # Unset is_default on the current default scenario
            all_scenarios = discover_scenarios()
            for s in all_scenarios:
                if s.is_default and s.slug != slug:
                    try:
                        other_doc, _ = _toml_open(s.slug)
                        if "scenario" in other_doc and "is_default" in other_doc.get("scenario", {}):
                            del other_doc["scenario"]["is_default"]
                            _backup_and_write_toml(other_doc, s.slug)
                    except Exception:
                        pass  # best-effort

        # Set/unset is_default on the target scenario
        doc, _ = _toml_open(slug)
        if "scenario" not in doc:
            doc["scenario"] = tomlkit.table()
        if is_default:
            doc["scenario"]["is_default"] = True
        else:
            if "is_default" in doc.get("scenario", {}):
                del doc["scenario"]["is_default"]

        _backup_and_write_toml(doc, slug)
        return JSONResponse({"ok": True, "is_default": is_default, "slug": slug})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── API: CSV source GET ─────────────────────────────────────────────────────


@app.get("/api/csv-source")
async def api_csv_source(request: Request) -> JSONResponse:
    """Return current [csv_source] data + per-account classification status."""
    scenario_slug = request.query_params.get("scenario") or None
    config_text = _read_config_text(scenario_slug)
    parsed = tomllib.loads(config_text)

    csv_source = parsed.get("csv_source", {})
    if not isinstance(csv_source, dict):
        csv_source = {}

    accounts_section = parsed.get("accounts", {})
    if not isinstance(accounts_section, dict):
        accounts_section = {}
    disabled = list(accounts_section.get("disabled", []))

    data_source = parsed.get("data_source", {})
    mode = "monarch"
    if isinstance(data_source, dict):
        mode = data_source.get("mode", "monarch")

    csv_accounts = csv_source.get("accounts", {})
    if not isinstance(csv_accounts, dict):
        csv_accounts = {}

    # Build per-account status list
    accounts_status: list[dict] = []
    for name in sorted(csv_accounts.keys()):
        balance = csv_accounts[name]
        cls = accounts_section.get(name)
        if isinstance(cls, dict):
            accounts_status.append({
                "name": name,
                "balance": balance,
                "classified": True,
                "category": cls.get("category"),
                "owner": cls.get("owner", "n/a"),
                "disabled": name in disabled,
            })
        elif isinstance(cls, str):
            accounts_status.append({
                "name": name,
                "balance": balance,
                "classified": cls != "unclassified",
                "category": cls,
                "owner": "n/a",
                "disabled": name in disabled,
            })
        else:
            accounts_status.append({
                "name": name,
                "balance": balance,
                "classified": False,
                "category": None,
                "owner": "n/a",
                "disabled": name in disabled,
            })

    return JSONResponse({
        "ok": True,
        "data_source_mode": mode,
        "csv_source": {
            "last_import": csv_source.get("last_import"),
            "account_count": len(csv_accounts),
        },
        "accounts": accounts_status,
    })


# ── API: CSV upload (parse, preview, merge) ────────────────────────────────


@app.post("/api/csv-upload")
async def api_csv_upload(request: Request) -> JSONResponse:
    """Accept a CSV file upload, parse it, and return a preview with per-account
    classification status.  If the scenario already has a [csv_source] section,
    merge is performed so new/updated/removed accounts are reported."""
    scenario_slug = request.query_params.get("scenario") or None

    try:
        form = await request.form()
        file = form.get("file")
        if file is None:
            return JSONResponse({"ok": False, "error": "No file uploaded."}, status_code=400)
        content = await file.read()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Failed to read upload: {exc}"}, status_code=400)

    # Write to a temporary file for parsing
    tmp = Path(f"/tmp/csv_upload_{scenario_slug or 'default'}_{os.urandom(4).hex()}.csv")
    try:
        tmp.write_bytes(content)

        parsed_accounts = parse_csv(str(tmp))

        # Load existing state for merge
        try:
            config_text = _read_config_text(scenario_slug)
            config = tomllib.loads(config_text)
            csv_source_config = config.get("csv_source", {})
            if not isinstance(csv_source_config, dict):
                csv_source_config = {}
            old_accounts = csv_source_config.get("accounts", {})
            if not isinstance(old_accounts, dict):
                old_accounts = {}
            accounts_section = config.get("accounts", {})
            if not isinstance(accounts_section, dict):
                accounts_section = {}
        except Exception:
            old_accounts = {}
            accounts_section = {}

        merge_result = merge_accounts(old_accounts, parsed_accounts, accounts_section)

        classification_map = {
            acct["name"]: accounts_section.get(acct["name"], "unclassified")
            for acct in parsed_accounts
        }
        earliest_date = min(a["date"] for a in parsed_accounts)
        latest_date = max(a["date"] for a in parsed_accounts)

        return JSONResponse({
            "ok": True,
            "total_accounts": len(parsed_accounts),
            "accounts": [
                {
                    "name": a["name"],
                    "balance": a["balance"],
                    "date": a["date"],
                    "classified": classification_map.get(a["name"], "unclassified") != "unclassified",
                }
                for a in parsed_accounts
            ],
            "merge": merge_result,
            "import_date": datetime.now().strftime("%Y-%m-%d"),
            "date_range": {"earliest": earliest_date, "latest": latest_date},
        })

    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Parse failed: {exc}"}, status_code=500)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


# ── API: save CSV source (write [csv_source] + [accounts] to TOML) ──────────


@app.post("/api/save-csv-source")
async def api_save_csv_source(request: Request) -> JSONResponse:
    """Save the [csv_source] section and account classifications to TOML.

    Expects JSON body:
    {
        "accounts": [
            {
                "name": "Checking - Joint",
                "balance": 5432.10,
                "category": "cash",
                "owner": "n/a",
                "disabled": false
            },
            ...
        ]
    }

    Writes [csv_source] (last_import, accounts), [accounts] (classification),
    and sets data_source.mode = "csv_import".
    """
    scenario_slug = request.query_params.get("scenario") or None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Request body must be JSON."}, status_code=400)

    entries: list[dict] | None = body.get("accounts")
    if entries is None:
        return JSONResponse({"ok": False, "error": "Missing 'accounts' list."}, status_code=400)

    if not entries:
        return JSONResponse({"ok": False, "error": "At least one account is required."}, status_code=400)

    doc, _ = _toml_open(scenario_slug)

    # ── 1. Build and write [csv_source] ────────────────────────────────────
    csv_src = tomlkit.table()
    csv_src["last_import"] = datetime.now().strftime("%Y-%m-%d")

    csv_accounts_tbl = tomlkit.table()
    for entry in entries:
        name: str = entry["name"]
        balance: float = entry.get("balance", 0.0)
        csv_accounts_tbl[name] = balance
    csv_src["accounts"] = csv_accounts_tbl
    doc["csv_source"] = csv_src

    # ── 2. Build and write [accounts] classification ───────────────────────
    disabled_names: list[str] = [e["name"] for e in entries if e.get("disabled")]
    active = [e for e in entries if not e.get("disabled")]

    if "accounts" not in doc or doc["accounts"] is None:
        doc["accounts"] = tomlkit.table()
    accounts = doc["accounts"]
    # Remove old account-name keys (keep disabled key if present)
    keys_to_remove = [k for k in accounts if k != "disabled"]
    for k in keys_to_remove:
        try:
            accounts.remove(k)
        except Exception:
            pass

    accounts["disabled"] = disabled_names
    for entry in active:
        name = entry["name"]
        category: str = entry.get("category", "ignore")
        owner: str = entry.get("owner", "n/a")
        if owner and owner != "n/a":
            accounts[name] = {"category": category, "owner": owner}
        else:
            accounts[name] = category

    # ── 3. Set data_source.mode ────────────────────────────────────────────
    if "data_source" not in doc or doc["data_source"] is None:
        doc["data_source"] = tomlkit.table()
    doc["data_source"]["mode"] = "csv_import"

    backup_path = _backup_and_write_toml(doc, scenario_slug)
    return JSONResponse({
        "ok": True,
        "message": f"CSV source saved for {len(entries)} account(s).",
        "backup_path": str(backup_path),
        "toml_content": doc.as_string(),
    })


# ── API: list available states (from tax table files) ────────────────────────────


@app.get("/api/tax-states")
async def api_tax_states() -> JSONResponse:
    """Return a list of available states and their tax table file names."""
    states: list[dict] = []
    if TAX_TABLES_DIR.exists():
        for fpath in sorted(TAX_TABLES_DIR.glob("2025_us_federal_*.toml")):
            slug = fpath.stem.replace("2025_us_federal_", "")
            try:
                with open(fpath, "rb") as f:
                    data = tomllib.load(f)
                state_info = data.get("taxes", {}).get("state", {})
                state_name = str(state_info.get("name", slug)).title()
                tax_ss = bool(state_info.get("tax_social_security", False))
                enabled = bool(state_info.get("enabled", False))
                bracket_count = len(state_info.get("brackets", {}).get("single", []))
            except Exception:
                state_name = slug.replace("_", " ").title()
                tax_ss = False
                enabled = False
                bracket_count = 0
            states.append({
                "slug": slug,
                "name": state_name,
                "file": fpath.name,
                "enabled": enabled,
                "tax_ss": tax_ss,
                "bracket_count": bracket_count,
            })
    return JSONResponse({"ok": True, "states": states})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("admin_app:app", host="0.0.0.0", port=8010, reload=False)
