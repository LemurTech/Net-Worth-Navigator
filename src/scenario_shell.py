"""Build the public scenario shell page for pre-rendered projections."""

from __future__ import annotations

import json
from pathlib import Path


def build_scenario_shell(
    *,
    manifest: dict,
    output_path: Path,
    manifest_relpath: str = "scenarios/index.json",
    editor_url: str = "/finances/config/",
) -> None:
    default_slug = str(manifest.get("default_slug", "default"))
    inline_manifest = json.dumps(manifest)
    shell_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Net Worth Navigator</title>
  <style>
    :root {{
      --bg: #08111d;
      --panel: rgba(15, 23, 37, 0.9);
      --panel-2: #111827;
      --text: #e5edf7;
      --muted: #9fb2c8;
      --border: #243142;
      --accent: #7dd3fc;
      --accent-strong: #0ea5e9;
      --shadow: 0 18px 40px rgba(0,0,0,.24);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(14,165,233,.16), transparent 28%),
        radial-gradient(circle at top right, rgba(56,189,248,.10), transparent 22%),
        linear-gradient(180deg, #08111d, #0b1220 46%, #08111d);
    }}
    .page {{
      width: 100%;
      padding: 10px 10px 14px;
    }}
    .topbar {{
      display: grid;
      gap: 10px;
      padding: 2px 2px 6px;
      margin-bottom: 6px;
    }}
    .topbar-title {{
      font-size: 28px;
      font-weight: 700;
      line-height: 1.02;
      letter-spacing: -0.03em;
    }}
    .selector-card {{
      display: grid;
      gap: 6px;
      min-width: 0;
    }}
    .control-row {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: nowrap;
    }}
    .selector-main {{
      min-width: 0;
      flex: 0 1 320px;
    }}
    select {{
      appearance: none;
      width: 100%;
      height: 42px;
      padding: 9px 40px 9px 14px;
      border-radius: 14px;
      border: 1px solid rgba(125, 211, 252, 0.18);
      background: linear-gradient(180deg, #101a2a, #0f1725);
      color: #f8fafc;
      font-size: 15px;
      font-weight: 600;
      line-height: 1.2;
      opacity: 1;
      -webkit-text-fill-color: #f8fafc;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
      text-shadow: none;
      background-image:
        linear-gradient(180deg, #101a2a, #0f1725),
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14'%3E%3Cpath d='M3 5.25 7 9l4-3.75' fill='none' stroke='%23f8fafc' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
      background-repeat: no-repeat, no-repeat;
      background-position: 0 0, right 14px center;
      background-size: auto, 14px 14px;
    }}
    select:focus {{
      outline: none;
      border-color: rgba(125, 211, 252, 0.6);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 0 0 3px rgba(14,165,233,0.16);
    }}
    select option {{
      color: #f8fafc;
      background: #101a2a;
    }}
    .scenario-summary {{
      min-width: 0;
      flex: 1 1 auto;
      display: flex;
      align-items: center;
    }}
    .scenario-desc {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
      max-width: none;
    }}
    .control-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: nowrap;
      align-items: center;
      flex: 0 0 auto;
    }}
    .linkbtn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 42px;
      padding: 0 14px;
      border: 1px solid rgba(125, 211, 252, 0.16);
      border-radius: 12px;
      color: var(--text);
      text-decoration: none;
      background: linear-gradient(180deg, rgba(22,34,52,0.96), rgba(20,31,48,0.86));
      font-size: 13px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      white-space: nowrap;
      transition: transform .14s ease, border-color .14s ease, background .14s ease;
    }}
    .linkbtn:hover {{
      border-color: var(--accent);
      transform: translateY(-1px);
    }}
    .linkbtn.primary {{
      background: linear-gradient(180deg, #1fb6ff, #0b8fd0);
      border-color: rgba(125, 211, 252, 0.8);
      color: #06111d;
      box-shadow: 0 10px 24px rgba(14,165,233,.24);
    }}
    .frame-card {{
      padding: 0;
      background: transparent;
      border: none;
      box-shadow: none;
      backdrop-filter: none;
    }}
    .frame-wrap {{
      border-radius: 0;
      overflow: hidden;
      border: none;
      background: transparent;
      min-height: 195vh;
    }}
    iframe {{
      display: block;
      width: 100%;
      height: 195vh;
      border: none;
      background: transparent;
    }}
    .empty-state {{
      display: none;
      padding: 56px 28px;
      text-align: center;
      color: var(--muted);
      font-size: 15px;
    }}
    .empty-state.active {{
      display: block;
    }}
    .frame-wrap.empty iframe {{
      display: none;
    }}
    .frame-note {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 11px;
      text-align: right;
      padding-right: 2px;
    }}
    @media (max-width: 980px) {{
      .topbar-title {{ font-size: 24px; }}
      .control-row {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        align-items: stretch;
      }}
      .selector-main {{ flex-basis: auto; }}
      .scenario-summary {{
        align-items: flex-start;
        order: 3;
      }}
      .control-actions {{
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-start;
      }}
      .linkbtn {{
        flex: 0 0 auto;
      }}
      .frame-wrap, iframe {{
        min-height: 175vh;
        height: 175vh;
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        padding: 8px 8px 12px;
      }}
      .topbar-title {{
        font-size: 22px;
      }}
      .scenario-desc {{
        font-size: 12px;
      }}
      .control-actions {{
        display: grid;
        grid-template-columns: 1fr 1fr;
      }}
      .linkbtn {{
        width: 100%;
      }}
    }}
    @media (max-width: 520px) {{
      .control-actions {{
        grid-template-columns: 1fr;
      }}
      .frame-wrap, iframe {{
        min-height: 150vh;
        height: 150vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="topbar">
      <div class="topbar-title">Net Worth Navigator</div>
      <div class="selector-card">
        <div class="control-row">
          <div class="selector-main">
            <select id="scenario-select" aria-label="Select scenario"></select>
          </div>
          <div class="scenario-summary">
            <div class="scenario-desc" id="scenario-description">Reading scenario manifest…</div>
          </div>
          <div class="control-actions">
            <a class="linkbtn" id="open-scenario-link" href="#" target="_blank" rel="noreferrer">Open Scenario Page</a>
            <button class="linkbtn" id="refresh-frame-btn" type="button">Refresh Frame</button>
            <a class="linkbtn primary" href="{editor_url}">Edit Scenarios</a>
          </div>
        </div>
      </div>
    </section>

    <section class="frame-card">
      <div class="frame-wrap" id="frame-wrap">
        <iframe id="scenario-frame" title="Scenario projection"></iframe>
        <div class="empty-state" id="empty-state">No rendered scenario is available yet. Save and render a scenario from the config editor to populate this page.</div>
      </div>
      <div class="frame-note">Manifest source: <code>{manifest_relpath}</code></div>
    </section>
  </div>

  <script>
    const inlineManifest = {inline_manifest};
    const manifestUrl = "{manifest_relpath}";
    const initialDefaultSlug = "{default_slug}";

    function getScenarioFromQuery() {{
      const params = new URLSearchParams(window.location.search);
      return params.get("scenario");
    }}

    function setQueryScenario(slug) {{
      const url = new URL(window.location.href);
      url.searchParams.set("scenario", slug);
      window.history.replaceState({{}}, "", url);
    }}

    function populateShell(manifest) {{
      const select = document.getElementById("scenario-select");
      const description = document.getElementById("scenario-description");
      const frame = document.getElementById("scenario-frame");
      const openLink = document.getElementById("open-scenario-link");
      const refreshButton = document.getElementById("refresh-frame-btn");
      const frameWrap = document.getElementById("frame-wrap");
      const emptyState = document.getElementById("empty-state");

      const scenarios = Array.isArray(manifest.scenarios) ? manifest.scenarios : [];

      select.innerHTML = "";
      scenarios.forEach((scenario) => {{
        const option = document.createElement("option");
        option.value = scenario.slug;
        option.textContent = scenario.name;
        select.appendChild(option);
      }});

      function projectionUrlFor(selected, {{ embed = false, force = false }} = {{}}) {{
        const base = selected.projection_path;
        const version = selected.rendered_at || manifest.generated_at || new Date().toISOString();
        const params = new URLSearchParams();
        if (embed) params.set("embed", "1");
        params.set("v", version);
        if (force) params.set("refresh", Date.now().toString());
        return `${{base}}?${{params.toString()}}`;
      }}

      function currentSelectedScenario() {{
        const slug = select.value || getScenarioFromQuery();
        return scenarios.find((scenario) => scenario.slug === slug) || null;
      }}

      function hardRefreshFrame() {{
        const selected = currentSelectedScenario();
        if (!selected) return;
        frame.src = projectionUrlFor(selected, {{ embed: true, force: true }});
      }}

      function activateScenario(slug) {{
        const selected = scenarios.find((scenario) => scenario.slug === slug) || scenarios.find((scenario) => scenario.slug === manifest.default_slug) || scenarios[0];
        if (!selected) {{
          frameWrap.classList.add("empty");
          emptyState.classList.add("active");
          description.textContent = "Render a scenario from the editor to populate the public selector.";
          frame.removeAttribute("src");
          openLink.setAttribute("href", "#");
          return;
        }}

        select.value = selected.slug;
        description.textContent = selected.description || "No description provided.";
        frame.src = projectionUrlFor(selected, {{ embed: true }});
        openLink.href = projectionUrlFor(selected, {{ embed: false }});
        frameWrap.classList.remove("empty");
        emptyState.classList.remove("active");
        setQueryScenario(selected.slug);
      }}

      select.addEventListener("change", () => activateScenario(select.value));
      refreshButton?.addEventListener("click", hardRefreshFrame);
      activateScenario(getScenarioFromQuery() || manifest.default_slug || initialDefaultSlug);
    }}

    fetch(manifestUrl, {{ cache: "no-store" }})
      .then((response) => response.ok ? response.json() : inlineManifest)
      .catch(() => inlineManifest)
      .then(populateShell);
  </script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(shell_html, encoding="utf-8")
