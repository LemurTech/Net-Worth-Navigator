from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import threading
import tomllib
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.config_loader import merge_tax_tables
from src.definitions_page import build_definitions_page_html
from src.scenarios import create_scenario_from_content, discover_scenarios, get_scenario, normalized_render_modes

APP_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = APP_ROOT / "output"
VENV_PYTHON = APP_ROOT / ".venv" / "bin" / "python"
PYTHON_BIN = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
RUN_SCRIPT = APP_ROOT / "run.py"
PUBLIC_PROJECTION_URL = "http://casalemuria.lan/finances/projection.html"
PUBLIC_EDITOR_URL = "http://casalemuria.lan/finances/config/"
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


def _prune_backups(backup_dir: Path, keep: int = 10) -> None:
    backups = sorted(
        backup_dir.glob("config-*.toml"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[keep:]:
        old_backup.unlink(missing_ok=True)


def _validate_config_text(content: str) -> dict:
    if not content.strip():
        raise ValueError("Configuration cannot be empty.")
    return merge_tax_tables(tomllib.loads(content))


def _backup_and_write(content: str, scenario_slug: str | None = None) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    backup_dir = _backup_dir(scenario_slug)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"config-{ts}.toml"
    backup_path.write_text(_read_config_text(scenario_slug), encoding="utf-8")
    _config_path(scenario_slug).write_text(content, encoding="utf-8")
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
    scenario_options = [
        {
            "slug": option.slug,
            "name": option.name,
            "description": option.description,
            "is_default": option.is_default,
        }
        for option in discovered_scenarios
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
    details_lines: list[str] = []
    for slug, result in results:
        details_lines.append(f"[{slug}] exit={result.returncode}")
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if stdout:
            details_lines.append(stdout)
        if stderr:
            details_lines.append(stderr)
    _update_render_job(job_id, scenario_slug=current_scenario_slug)
    _complete_render_job(
        job_id,
        state="failed" if failures else "completed",
        status_kind="error" if failures else "success",
        status_title="Render all completed with errors" if failures else "Render all complete",
        status_message=(
            f"Saved current scenario and rendered {len(results)} scenario(s), with {len(failures)} failure(s)."
            if failures
            else f"Saved current scenario and rendered {len(results)} scenario(s) successfully."
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


@app.get("/", response_class=HTMLResponse)
async def editor_home(request: Request) -> HTMLResponse:
    scenario_slug = request.query_params.get("scenario")
    job_id = request.query_params.get("job")
    content = _read_config_text(scenario_slug)
    completed_job_context = _job_context_from_completed_job(job_id) if job_id else None
    context = _build_context(
        request,
        content=content,
        status_kind=(completed_job_context or {}).get("status_kind", "info"),
        status_title=(completed_job_context or {}).get("status_title", "Ready"),
        status_message=(completed_job_context or {}).get("status_message", "Load, edit, validate, save, or save and re-render the offline projection."),
        details=(completed_job_context or {}).get("details"),
        backup_path=(completed_job_context or {}).get("backup_path"),
        scenario_slug=scenario_slug,
        last_action=(completed_job_context or {}).get("last_action", ""),
        clone_name="",
        clone_slug="",
        clone_description="",
    )
    return templates.TemplateResponse(request, "config_editor.html", context)


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
            clone_render = _render_projection_offline(created.slug)
            if clone_render.returncode != 0:
                details = "\n".join(
                    part for part in [
                        (clone_render.stdout or "").strip(),
                        (clone_render.stderr or "").strip(),
                    ] if part
                ).strip()
                context = _build_context(
                    request,
                    content=content,
                    status_kind="error",
                    status_title="Scenario cloned but render failed",
                    status_message=f"Created scenario '{created.name}' ({created.slug}), but its initial render failed.",
                    details=details or "No process output captured.",
                    scenario_slug=created.slug,
                    last_action=action,
                    clone_name="",
                    clone_slug="",
                    clone_description="",
                )
                return templates.TemplateResponse(request, "config_editor.html", context, status_code=500)

            cloned_content = _read_config_text(created.slug)
            context = _build_context(
                request,
                content=cloned_content,
                status_kind="success",
                status_title="Scenario cloned",
                status_message=f"Created and rendered scenario '{created.name}' ({created.slug}).",
                details=(clone_render.stdout or "").strip() or None,
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("admin_app:app", host="0.0.0.0", port=8010, reload=False)
