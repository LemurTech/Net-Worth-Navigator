from __future__ import annotations

import html
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.config_loader import merge_tax_tables
from src.scenarios import create_scenario_from_content, discover_scenarios, get_scenario

APP_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = APP_ROOT / "output"
VENV_PYTHON = APP_ROOT / ".venv" / "bin" / "python"
PYTHON_BIN = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
RUN_SCRIPT = APP_ROOT / "run.py"
PUBLIC_PROJECTION_URL = "http://casalemuria.lan/finances/projection.html"
PUBLIC_EDITOR_URL = "http://casalemuria.lan/finances/config/"

app = FastAPI(title="Net Worth Navigator Config Editor")
templates = Jinja2Templates(directory=str(APP_ROOT / "templates"))


def _current_scenario(scenario_slug: str | None = None):
    return get_scenario(scenario_slug)


def _config_path(scenario_slug: str | None = None) -> Path:
    return _current_scenario(scenario_slug).config_path


def _backup_dir(scenario_slug: str | None = None) -> Path:
    return OUTPUT_DIR / "config-backups" / _current_scenario(scenario_slug).slug


def _read_config_text(scenario_slug: str | None = None) -> str:
    return _config_path(scenario_slug).read_text(encoding="utf-8")


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


def _render_all_scenarios() -> list[tuple[str, subprocess.CompletedProcess[str]]]:
    results = []
    for scenario in discover_scenarios():
        results.append((scenario.slug, _render_projection_offline(scenario.slug)))
    return results


def _build_context(request: Request, *, content: str, status_kind: str = "info",
                   status_title: str | None = None, status_message: str | None = None,
                   details: str | None = None, backup_path: str | None = None,
                   scenario_slug: str | None = None,
                   clone_name: str = "",
                   clone_slug: str = "",
                   clone_description: str = "") -> dict:
    scenario = _current_scenario(scenario_slug)
    config_path = _config_path(scenario_slug)
    scenario_options = [
        {
            "slug": option.slug,
            "name": option.name,
            "description": option.description,
            "is_default": option.is_default,
        }
        for option in discover_scenarios()
    ]
    last_modified = datetime.fromtimestamp(config_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "request": request,
        "content": content,
        "status_kind": status_kind,
        "status_title": status_title,
        "status_message": status_message,
        "details": details,
        "backup_path": backup_path,
        "backup_dir": str(_backup_dir(scenario.slug)),
        "config_path": str(config_path),
        "scenario_name": scenario.name,
        "scenario_slug": scenario.slug,
        "scenario_options": scenario_options,
        "clone_name": clone_name,
        "clone_slug": clone_slug,
        "clone_description": clone_description,
        "last_modified": last_modified,
        "projection_url": PUBLIC_PROJECTION_URL,
        "editor_url": PUBLIC_EDITOR_URL,
    }


async def _parse_form(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


@app.get("/", response_class=HTMLResponse)
async def editor_home(request: Request) -> HTMLResponse:
    scenario_slug = request.query_params.get("scenario")
    content = _read_config_text(scenario_slug)
    context = _build_context(
        request,
        content=content,
        status_kind="info",
        status_title="Ready",
        status_message="Load, edit, validate, save, or save and re-render the offline projection.",
        scenario_slug=scenario_slug,
        clone_name="",
        clone_slug="",
        clone_description="",
    )
    return templates.TemplateResponse(request, "config_editor.html", context)


@app.post("/", response_class=HTMLResponse)
async def editor_submit(request: Request) -> HTMLResponse:
    form = await _parse_form(request)
    action = form.get("action", "validate")
    content = form.get("content", "")
    scenario_slug = form.get("scenario_slug") or None
    clone_name = form.get("clone_name", "")
    clone_slug = form.get("clone_slug", "")
    clone_description = form.get("clone_description", "")

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
                status_message=f"Created scenario '{created.name}' ({created.slug}).",
                scenario_slug=created.slug,
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
                clone_name=clone_name,
                clone_slug=clone_slug,
                clone_description=clone_description,
            )
            return templates.TemplateResponse(request, "config_editor.html", context)

        if action == "save_render":
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
                clone_name=clone_name,
                clone_slug=clone_slug,
                clone_description=clone_description,
            )
            return templates.TemplateResponse(request, "config_editor.html", context, status_code=500)

        if action == "save_render_all":
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
        "projection_url": PUBLIC_PROJECTION_URL,
        "editor_url": PUBLIC_EDITOR_URL,
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("admin_app:app", host="0.0.0.0", port=8010, reload=False)
