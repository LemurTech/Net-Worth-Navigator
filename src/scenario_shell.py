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
      flex: 0 0 320px;
    }}
    select {{
      width: 100%;
      height: 42px;
      padding: 10px 14px;
      border-radius: 14px;
      border: 1px solid rgba(125, 211, 252, 0.18);
      background: linear-gradient(180deg, #101a2a, #0f1725);
      color: #f8fafc;
      font-size: 15px;
      font-weight: 600;
      opacity: 1;
      -webkit-text-fill-color: #f8fafc;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
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
      min-height: 156vh;
    }}
    iframe {{
      display: block;
      width: 100%;
      height: 156vh;
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
      .control-row {{ align-items: stretch; }}
      .selector-main {{ flex-basis: 100%; }}
      .scenario-summary {{ align-items: flex-start; }}
      .control-actions {{ flex-wrap: wrap; }}
      .frame-wrap, iframe {{
        min-height: 140vh;
        height: 140vh;
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
        frame.src = selected.projection_path + "?embed=1";
        openLink.href = selected.projection_path;
        frameWrap.classList.remove("empty");
        emptyState.classList.remove("active");
        setQueryScenario(selected.slug);
      }}

      select.addEventListener("change", () => activateScenario(select.value));
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
