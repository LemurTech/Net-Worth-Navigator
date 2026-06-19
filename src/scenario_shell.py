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
      --panel: #0f1725;
      --panel-2: #111827;
      --text: #e5edf7;
      --muted: #9fb2c8;
      --border: #243142;
      --accent: #7dd3fc;
      --shadow: 0 18px 40px rgba(0,0,0,.30);
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
      padding: 10px 10px 16px;
    }}
    .topbar, .frame-card {{
      background: rgba(15, 23, 37, 0.92);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 14px 30px rgba(0,0,0,.24);
      backdrop-filter: blur(12px);
    }}
    .topbar {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 420px) auto;
      gap: 14px;
      align-items: center;
      padding: 12px 14px;
      margin-bottom: 10px;
    }}
    .brand {{
      min-width: 0;
    }}
    .brand h1 {{
      margin: 0 0 4px;
      font-size: clamp(22px, 2.2vw, 30px);
      line-height: 1.02;
      letter-spacing: -0.03em;
    }}
    .brand p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.4;
      max-width: 760px;
    }}
    .topbar-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .meta-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(17,24,39,.78);
      color: #d4e6f7;
      font-size: 12px;
    }}
    .selector-card {{
      display: grid;
      gap: 8px;
      min-width: 0;
    }}
    .control-label {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    select {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #111827;
      color: var(--text);
      font-size: 14px;
    }}
    .scenario-name {{
      font-size: 17px;
      font-weight: 700;
      line-height: 1.1;
    }}
    .scenario-desc {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      min-height: 0;
    }}
    .control-actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .linkbtn {{
      display: inline-block;
      padding: 9px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      color: var(--text);
      text-decoration: none;
      background: #162234;
      font-size: 13px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .linkbtn:hover {{
      border-color: var(--accent);
    }}
    .linkbtn.primary {{
      background: linear-gradient(180deg, #0ea5e9, #0284c7);
      border-color: #38bdf8;
      color: #08111d;
    }}
    .frame-card {{
      padding: 8px;
    }}
    .frame-wrap {{
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #1f2a3a;
      background: #0a1220;
      min-height: 156vh;
    }}
    iframe {{
      display: block;
      width: 100%;
      height: 156vh;
      border: none;
      background: #0a1220;
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
    }}
    @media (max-width: 980px) {{
      .topbar {{
        grid-template-columns: 1fr;
      }}
      .frame-wrap, iframe {{
        min-height: 112vh;
        height: 112vh;
      }}
      .control-actions {{ justify-content: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="topbar">
      <div class="brand">
        <h1>Net Worth Navigator</h1>
        <p>Switch between pre-rendered scenarios without waiting on a fresh run.</p>
        <div class="topbar-meta">
          <div class="meta-pill" id="manifest-generated-at">Manifest pending</div>
          <div class="meta-pill" id="scenario-count-pill">0 scenarios</div>
        </div>
      </div>
      <div class="selector-card">
          <div class="control-label">Scenario</div>
          <select id="scenario-select" aria-label="Select scenario"></select>
          <div class="scenario-name" id="scenario-name">Loading…</div>
          <div class="scenario-desc" id="scenario-description">Reading scenario manifest…</div>
      </div>
      <div class="control-actions">
        <a class="linkbtn primary" href="{editor_url}">Edit Scenarios</a>
        <a class="linkbtn" id="open-scenario-link" href="#" target="_blank" rel="noreferrer">Open Scenario Page</a>
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
      const name = document.getElementById("scenario-name");
      const description = document.getElementById("scenario-description");
      const frame = document.getElementById("scenario-frame");
      const openLink = document.getElementById("open-scenario-link");
      const generatedAt = document.getElementById("manifest-generated-at");
      const countPill = document.getElementById("scenario-count-pill");
      const frameWrap = document.getElementById("frame-wrap");
      const emptyState = document.getElementById("empty-state");

      const scenarios = Array.isArray(manifest.scenarios) ? manifest.scenarios : [];
      generatedAt.textContent = manifest.generated_at ? "Manifest " + manifest.generated_at.replace("T", " ").slice(0, 19) : "Manifest ready";
      countPill.textContent = scenarios.length + (scenarios.length === 1 ? " scenario" : " scenarios");

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
          name.textContent = "No scenarios found";
          description.textContent = "Render a scenario from the editor to populate the public selector.";
          frame.removeAttribute("src");
          openLink.setAttribute("href", "#");
          return;
        }}

        select.value = selected.slug;
        name.textContent = selected.name;
        description.textContent = selected.description || "No description provided.";
        frame.src = selected.projection_path;
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
