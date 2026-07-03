"""Build the public scenario shell page and comparison page for pre-rendered projections."""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Colour palette assigned to each scenario slot (up to 10 scenarios).
# These are Plotly-safe CSS colour strings used in both the chart and chip UI.
# ---------------------------------------------------------------------------
_SCENARIO_COLORS = [
    "#7dd3fc",  # sky-300
    "#86efac",  # green-300
    "#fbbf24",  # amber-400
    "#f87171",  # red-400
    "#c084fc",  # purple-400
    "#34d399",  # emerald-400
    "#fb923c",  # orange-400
    "#a78bfa",  # violet-400
    "#f472b6",  # pink-400
    "#94a3b8",  # slate-400
]


def build_scenario_shell(
    *,
    manifest: dict,
    output_path: Path,
    manifest_relpath: str = "scenarios/index.json",
    setup_url: str = "/finances/config/setup",
    definitions_url: str = "/finances/definitions.html",
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
      flex-wrap: wrap;
    }}
    .selector-group {{
      display: flex;
      gap: 10px;
      flex: 1 1 420px;
      min-width: 0;
    }}
    .selector-main {{
      min-width: 0;
      flex: 1 1 0;
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
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
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
    .linkbtn-short {{ display: none; }}
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
    #help-mode-toggle {{
      width: 42px;
      padding: 0;
      font-size: 18px;
      font-weight: 600;
    }}
    #help-mode-toggle.active {{
      background: #0369a1;
      border-color: #0369a1;
      color: #fff;
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
      .scenario-summary {{
        align-items: flex-start;
        order: 3;
        flex-basis: 100%;
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
    /* Plan Name / Plan Type stay on one line at virtually all widths — select
       text ellipsizes instead of forcing a stack. Only the narrowest phones
       (< 360px, smaller than any current production device) fall back to a
       vertical stack, since below that width even ellipsized selects become
       too cramped to tap accurately. */
    @media (max-width: 359px) {{
      .selector-group {{
        flex-direction: column;
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
      select {{
        font-size: 13px;
        padding: 8px 32px 8px 10px;
        background-position: 0 0, right 10px center;
      }}
      .control-actions {{
        display: flex;
        flex-wrap: nowrap;
        gap: 6px;
        width: 100%;
        flex-basis: 100%;
      }}
      .linkbtn, #help-mode-toggle {{
        width: auto;
        flex: 1 1 0;
        min-width: 0;
        padding: 0 6px;
        font-size: 12.5px;
      }}
      .linkbtn-full {{ display: none; }}
      .linkbtn-short {{ display: inline; }}
    }}
    @media (max-width: 520px) {{
      .frame-wrap, iframe {{
        min-height: 150vh;
        height: 150vh;
      }}
    }}
    /* Data freshness indicator — hidden by default, shown by JS only when cache exists */
    .freshness-bar {{ display: none; align-items: center; gap: 6px;
                     margin: 2px 0 4px; padding: 0 2px;
                     font-size: 11px; color: var(--muted); }}
    .freshness-bar.visible {{ display: flex; }}
    .freshness-bar .dot {{ display: inline-block; width: 7px; height: 7px;
                          border-radius: 50%; flex-shrink: 0; }}
    .freshness-bar .dot.healthy {{ background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.50); }}
    .freshness-bar .dot.stale {{ background: #fbbf24; box-shadow: 0 0 6px rgba(251,191,36,0.50); }}
    .freshness-bar .dot.missing {{ background: #64748b; }}
    .freshness-bar .label {{ color: var(--muted); }}
    /* First-time welcome overlay — rendered in the SHELL page (not the embedded
       iframe) so position:fixed centers against the real browser viewport
       instead of the iframe's own (much taller) box. */
    .welcome-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                       background: rgba(0, 0, 0, 0.85); z-index: 20000;
                       display: flex; align-items: center; justify-content: center;
                       animation: fadeIn 0.3s ease-out; }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .welcome-content {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                       border: 2px solid #0284c7; border-radius: 12px; padding: 32px 40px;
                       /* This page has a global box-sizing:border-box reset (unlike the
                          standalone projection page), so max-width must include padding+
                          border to render the same content width: 620 + 2*40 + 2*2 = 704. */
                       max-width: 704px; width: 90vw; color: #e2e8f0; box-shadow: 0 20px 60px rgba(0,0,0,0.6); }}
    .welcome-content h2 {{ margin: 0 0 16px 0; color: #7dd3fc; font-size: 24px;
                          display: flex; align-items: center; gap: 12px; }}
    .welcome-content h2::before {{ content: '👋'; font-size: 28px; }}
    .welcome-content p {{ margin: 0 0 20px 0; line-height: 1.6; color: #cbd5e1; }}
    .welcome-highlights {{ list-style: none; padding: 0; margin: 0 0 24px 0; }}
    .welcome-highlights li {{ padding: 10px 0; border-bottom: 1px solid #334155;
                             display: flex; align-items: start; gap: 12px; }}
    .welcome-highlights li:last-child {{ border-bottom: none; }}
    .welcome-highlights li::before {{ content: '✓'; color: #10b981; font-weight: 700;
                                     font-size: 18px; flex-shrink: 0; }}
    .welcome-actions {{ display: flex; gap: 12px; justify-content: flex-end; }}
    .welcome-btn {{ padding: 10px 20px; border-radius: 6px; font-size: 14px;
                   font-weight: 600; cursor: pointer; transition: all 0.2s;
                   border: 1px solid transparent; }}
    .welcome-btn-primary {{ background: #0284c7; color: #fff; border-color: #0369a1; }}
    .welcome-btn-primary:hover {{ background: #0369a1; }}
    .welcome-btn-secondary {{ background: transparent; color: #94a3b8;
                             border-color: #475569; }}
    .welcome-btn-secondary:hover {{ border-color: #64748b; color: #cbd5e1; }}
  </style>
</head>
<body>
  <div class="page">
    <section class="topbar">
      <div class="topbar-title">Net Worth Navigator</div>
      <div class="freshness-bar" id="freshness-bar">
        <span class="dot missing" id="freshness-dot"></span>
        <span class="label" id="freshness-label">Syncing data…</span>
      </div>
      <div class="selector-card">
        <div class="control-row">
          <div class="selector-group">
            <div class="selector-main">
              <select id="scenario-select" aria-label="Select scenario"></select>
            </div>
            <div class="selector-main">
              <select id="mode-select" aria-label="Select mode"></select>
            </div>
          </div>
          <div class="scenario-summary">
            <div class="scenario-desc" id="scenario-description">Reading scenario manifest…</div>
          </div>
          <div class="control-actions">
            <a class="linkbtn" id="open-scenario-link" href="#" target="_blank" rel="noreferrer">
              <span class="linkbtn-full">Open Scenario Page</span><span class="linkbtn-short">Open</span>
            </a>
            <a class="linkbtn" id="compare-link" href="/finances/compare.html" target="_blank" rel="noreferrer">
              <span class="linkbtn-full">Compare Scenarios</span><span class="linkbtn-short">Compare</span>
            </a>
            <button class="linkbtn" id="help-mode-toggle" type="button" title="Toggle help tooltips">?</button>
            <a class="linkbtn primary" id="setup-scenarios-link" href="{setup_url}">
              <span class="linkbtn-full">Scenario Setup</span><span class="linkbtn-short">Setup</span>
            </a>
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

    function getModeFromQuery() {{
      const params = new URLSearchParams(window.location.search);
      return params.get("mode");
    }}

    function setQueryState(slug, mode) {{
      const url = new URL(window.location.href);
      url.searchParams.set("scenario", slug);
      if (mode) {{
        url.searchParams.set("mode", mode);
      }} else {{
        url.searchParams.delete("mode");
      }}
      window.history.replaceState({{}}, "", url);
    }}

    // Help mode toggle — syncs state to the embedded scenario iframe via postMessage.
    (function initHelpModeToggle() {{
      const helpBtn = document.getElementById("help-mode-toggle");
      const frame = document.getElementById("scenario-frame");
      if (!helpBtn || !frame) return;

      const helpModeActive = localStorage.getItem("nwn-help-mode") === "true";
      if (helpModeActive) {{
        helpBtn.classList.add("active");
      }}

      helpBtn.addEventListener("click", function() {{
        const isActive = helpBtn.classList.toggle("active");
        localStorage.setItem("nwn-help-mode", isActive ? "true" : "false");
        if (frame.contentWindow) {{
          frame.contentWindow.postMessage({{ type: "toggle-help-mode", active: isActive }}, "*");
        }}
      }});

      // Re-apply help mode whenever a new scenario/mode is loaded into the iframe.
      frame.addEventListener("load", function() {{
        const active = localStorage.getItem("nwn-help-mode") === "true";
        if (active && frame.contentWindow) {{
          setTimeout(function() {{
            frame.contentWindow.postMessage({{ type: "toggle-help-mode", active: true }}, "*");
          }}, 100);
        }}
      }});
    }})();

    // First-time welcome overlay — the embedded projection page asks the shell
    // (this page) to display it, since position:fixed inside the iframe centers
    // against the iframe's own tall box rather than the visible viewport.
    function showWelcomeOverlay() {{
      if (document.querySelector(".welcome-overlay")) return;
      const overlay = document.createElement("div");
      overlay.className = "welcome-overlay";

      const content = document.createElement("div");
      content.className = "welcome-content";
      content.innerHTML = `
        <h2>Welcome to Your Retirement Projection!</h2>
        <p>Here's a quick tour of the key features:</p>
        <ul class="welcome-highlights">
          <li><strong>Your chart shows net worth over time</strong> — Hover over any point to see details</li>
          <li><strong>Click year columns in tables</strong> to highlight that year across all data</li>
          <li><strong>Switch tabs below</strong> to explore detailed breakdowns (Accounts, Cash Flow, Tax, etc.)</li>
          <li><strong>Need help?</strong> Click the <strong>?</strong> button to enable contextual tooltips</li>
        </ul>
        <div class="welcome-actions">
          <button class="welcome-btn welcome-btn-secondary" id="welcome-later">Remind me later</button>
          <button class="welcome-btn welcome-btn-primary" id="welcome-dismiss">Got it, don't show again</button>
        </div>
      `;

      overlay.appendChild(content);
      document.body.appendChild(overlay);

      document.getElementById("welcome-dismiss").addEventListener("click", function() {{
        localStorage.setItem("nwn-welcome-seen", "true");
        document.body.removeChild(overlay);
      }});
      document.getElementById("welcome-later").addEventListener("click", function() {{
        document.body.removeChild(overlay);
      }});
      overlay.addEventListener("click", function(e) {{
        if (e.target === overlay) document.body.removeChild(overlay);
      }});
    }}

    window.addEventListener("message", function(event) {{
      if (event.data && event.data.type === "show-welcome-overlay") {{
        showWelcomeOverlay();
      }}
    }});

    function populateShell(manifest) {{
      const select = document.getElementById("scenario-select");
      const modeSelect = document.getElementById("mode-select");
      const description = document.getElementById("scenario-description");
      const frame = document.getElementById("scenario-frame");
      const openLink = document.getElementById("open-scenario-link");
      const frameWrap = document.getElementById("frame-wrap");
      const emptyState = document.getElementById("empty-state");

      // Data freshness indicator — updates when scenario changes
      function updateFreshnessForScenario(scenario) {{
        const bar = document.getElementById("freshness-bar");
        const dot = document.getElementById("freshness-dot");
        const label = document.getElementById("freshness-label");
        if (!bar || !dot || !label) return;
        // Hide for synthetic scenarios (no live Monarch data)
        if (!scenario || scenario.data_source_mode === "synthetic") {{
          bar.classList.remove("visible");
          return;
        }}
        const ts = manifest.cache_timestamp;
        if (!ts) {{
          bar.classList.remove("visible");
          return;
        }}
        bar.classList.add("visible");
        const cacheDate = new Date(ts);
        const now = new Date();
        const daysOld = (now - cacheDate) / (1000 * 60 * 60 * 24);
        const dateStr = cacheDate.toLocaleDateString("en-US", {{
          year: "numeric", month: "short", day: "numeric",
        }});
        if (daysOld > 30) {{
          dot.className = "dot stale";
          label.textContent = "Balances: " + dateStr + " (stale — " + Math.round(daysOld) + " days old)";
        }} else {{
          dot.className = "dot healthy";
          label.textContent = "Live balances: " + dateStr;
        }}
      }}

      const scenarios = Array.isArray(manifest.scenarios) ? manifest.scenarios : [];

      select.innerHTML = "";
      scenarios.forEach((scenario) => {{
        const option = document.createElement("option");
        option.value = scenario.slug;
        option.textContent = scenario.name;
        select.appendChild(option);
      }});

      function modeEntryFor(selectedScenario, mode) {{
        const modes = Array.isArray(selectedScenario?.modes) ? selectedScenario.modes : [];
        return modes.find((entry) => entry.mode === mode) || modes.find((entry) => entry.mode === selectedScenario?.default_mode) || modes[0] || null;
      }}

      function projectionUrlFor(selectedScenario, selectedMode, {{ embed = false, force = false }} = {{}}) {{
        const selected = modeEntryFor(selectedScenario, selectedMode);
        if (!selected) return "#";
        const base = selected.projection_path;
        const version = selected.rendered_at || manifest.generated_at || new Date().toISOString();
        const params = new URLSearchParams();
        if (embed) params.set("embed", "1");
        params.set("v", version);
        if (force) params.set("refresh", Date.now().toString());
        return `${{base}}?${{params.toString()}}`;
      }}

      function setupUrlFor(selected) {{
        const url = new URL("{setup_url}", window.location.origin);
        if (selected && selected.slug) {{
          url.searchParams.set("scenario", selected.slug);
        }}
        return url.toString();
      }}

      function populateModeOptions(selectedScenario, requestedMode) {{
        const modes = Array.isArray(selectedScenario?.modes) ? selectedScenario.modes : [];
        modeSelect.innerHTML = "";
        modes.forEach((entry) => {{
          const option = document.createElement("option");
          option.value = entry.mode;
          option.textContent = entry.label;
          modeSelect.appendChild(option);
        }});
        const resolvedMode = modeEntryFor(selectedScenario, requestedMode)?.mode || "";
        if (resolvedMode) {{
          modeSelect.value = resolvedMode;
        }}
        modeSelect.disabled = modes.length <= 1;
        return resolvedMode;
      }}

      function activateScenario(slug, requestedMode = null) {{
        const selected = scenarios.find((scenario) => scenario.slug === slug) || scenarios.find((scenario) => scenario.slug === manifest.default_slug) || scenarios[0];
        if (!selected) {{
          frameWrap.classList.add("empty");
          emptyState.classList.add("active");
          description.textContent = "Render a scenario from the editor to populate the public selector.";
          frame.removeAttribute("src");
          openLink.setAttribute("href", "#");
          modeSelect.innerHTML = "";
          modeSelect.disabled = true;
          const emptySetupLink = document.getElementById("setup-scenarios-link");
          if (emptySetupLink) {{
            emptySetupLink.setAttribute("href", "{setup_url}");
          }}
          return;
        }}

        select.value = selected.slug;
        const resolvedMode = populateModeOptions(selected, requestedMode || getModeFromQuery() || selected.default_mode);
        const selectedModeEntry = modeEntryFor(selected, resolvedMode);
        const modeLabel = selectedModeEntry?.label || "Mode unavailable";
        const scenarioText = selected.description || "No description provided.";
        description.textContent = scenarioText;
        frame.src = projectionUrlFor(selected, resolvedMode, {{ embed: true }});
        openLink.href = projectionUrlFor(selected, resolvedMode, {{ embed: false }});
        const setupLink = document.getElementById("setup-scenarios-link");
        if (setupLink) {{
          setupLink.href = setupUrlFor(selected);
        }}
        frameWrap.classList.remove("empty");
        emptyState.classList.remove("active");
        setQueryState(selected.slug, resolvedMode);

        // Keep Compare Scenarios link scoped to the active scenario vs default
        const compareLink = document.getElementById("compare-link");
        if (compareLink) {{
          const defaultSlug = manifest.default_slug || "";
          const compareUrl = new URL("/finances/compare.html", window.location.origin);
          compareUrl.searchParams.set("a", selected.slug);
          if (selected.slug !== defaultSlug && defaultSlug) {{
            compareUrl.searchParams.set("b", defaultSlug);
          }}
          compareLink.href = compareUrl.toString();
        }}
        updateFreshnessForScenario(selected);
      }}

      select.addEventListener("change", () => activateScenario(select.value));
      modeSelect.addEventListener("change", () => activateScenario(select.value, modeSelect.value));
      activateScenario(getScenarioFromQuery() || manifest.default_slug || initialDefaultSlug, getModeFromQuery());
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


# ---------------------------------------------------------------------------
# build_compare_page
# ---------------------------------------------------------------------------

def build_compare_page(
    *,
    manifest: dict,
    output_path: Path,
    manifest_relpath: str = "scenarios/index.json",
    shell_url: str = "/finances/projection.html",
    definitions_url: str = "/finances/definitions.html",
) -> None:
    """Generate a self-contained scenario comparison page.

    The page fetches sidecar CSVs and simulation_summary.json at runtime so it
    always reflects the latest renders without requiring a Python rebuild.
    Plotly is loaded from CDN.
    """
    inline_manifest = json.dumps(manifest)
    colors_js = json.dumps(_SCENARIO_COLORS)

    compare_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NWN — Compare Scenarios</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>
  <style>
    :root {{
      --bg: #08111d;
      --panel: rgba(15,23,37,0.9);
      --panel-2: #111827;
      --text: #e5edf7;
      --muted: #9fb2c8;
      --border: #243142;
      --accent: #7dd3fc;
      --accent-strong: #0ea5e9;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(14,165,233,.14), transparent 26%),
        radial-gradient(circle at top right, rgba(56,189,248,.09), transparent 20%),
        linear-gradient(180deg, #08111d, #0b1220 46%, #08111d);
      min-height: 100vh;
    }}
    .page {{ max-width: 1280px; margin: 0 auto; padding: 18px 16px 40px; }}
    .topbar {{ display: flex; align-items: baseline; gap: 14px; margin-bottom: 18px; flex-wrap: wrap; }}
    .topbar-title {{ font-size: 22px; font-weight: 700; letter-spacing: -.03em; }}
    .topbar-sub {{ color: var(--muted); font-size: 13px; }}
    .back-link {{ color: var(--accent); font-size: 13px; font-weight: 600; text-decoration: none; margin-left: auto; white-space: nowrap; }}
    .back-link:hover {{ color: #fff; }}

    /* ── Controls ───────────────────────────────────────────────── */
    .controls {{ display: flex; gap: 14px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 16px; }}
    .control-group {{ display: flex; flex-direction: column; gap: 6px; }}
    .control-label {{ font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }}
    .chip-row {{ display: flex; gap: 7px; flex-wrap: wrap; }}
    .chip {{
      display: inline-flex; align-items: center; gap: 5px;
      padding: 5px 11px; border-radius: 20px; font-size: 12px; font-weight: 600;
      border: 1.5px solid transparent; cursor: pointer; transition: opacity .14s, transform .1s;
      background: rgba(36,49,66,0.7); color: var(--muted);
      white-space: nowrap; user-select: none;
    }}
    .chip.active {{ color: #06111d; }}
    .chip:hover {{ transform: translateY(-1px); opacity: .9; }}
    .chip .chip-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      flex-shrink: 0;
    }}
    select.mode-select {{
      appearance: none; height: 36px; padding: 6px 34px 6px 12px;
      border-radius: 10px; border: 1px solid rgba(125,211,252,.2);
      background: linear-gradient(180deg, #101a2a, #0f1725),
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 14 14'%3E%3Cpath d='M3 5.25 7 9l4-3.75' fill='none' stroke='%23f8fafc' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
      background-repeat: no-repeat, no-repeat;
      background-position: 0 0, right 10px center;
      background-size: auto, 12px 12px;
      color: #f8fafc; -webkit-text-fill-color: #f8fafc; opacity: 1; text-shadow: none;
      font-size: 13px; font-weight: 600; font-family: inherit; cursor: pointer;
    }}
    select.mode-select:focus {{ outline: none; border-color: rgba(125,211,252,.55); }}
    select.mode-select option {{ background: #101a2a; }}

    /* ── Chart card ─────────────────────────────────────────────── */
    .card {{
      background: var(--panel-2); border: 1px solid var(--border);
      border-radius: 16px; padding: 18px 16px; margin-bottom: 16px;
    }}
    .card-title {{ font-size: 14px; font-weight: 700; color: var(--accent); margin-bottom: 12px; }}
    #compare-chart {{ width: 100%; height: 420px; }}

    /* ── KPI table ──────────────────────────────────────────────── */
    .kpi-table-wrap {{ overflow-x: auto; }}
    table.kpi {{
      width: 100%; border-collapse: collapse; font-size: 13px;
      min-width: 640px;
    }}
    table.kpi th {{
      text-align: left; padding: 8px 12px; font-size: 11px; font-weight: 700;
      color: var(--muted); text-transform: uppercase; letter-spacing: .06em;
      border-bottom: 1px solid var(--border); white-space: nowrap;
    }}
    table.kpi td {{
      padding: 9px 12px; border-bottom: 1px solid rgba(36,49,66,.6);
      white-space: nowrap;
    }}
    table.kpi tr:last-child td {{ border-bottom: none; }}
    table.kpi tr:hover td {{ background: rgba(125,211,252,.04); }}
    .kpi-name {{ font-weight: 600; }}
    .kpi-swatch {{
      display: inline-block; width: 10px; height: 10px; border-radius: 2px;
      margin-right: 6px; vertical-align: middle; flex-shrink: 0;
    }}
    .kpi-num {{ font-variant-numeric: tabular-nums; font-family: "SF Mono", "Fira Mono", monospace; font-size: 12px; }}
    .delta-pos {{ color: #86efac; }}
    .delta-neg {{ color: #f87171; }}
    .delta-neu {{ color: var(--muted); }}
    .kpi-default-marker {{ font-size: 10px; color: var(--accent); margin-left: 4px; }}
    .loading-msg {{ color: var(--muted); font-size: 13px; padding: 12px 0; }}
    .error-msg {{ color: #f87171; font-size: 13px; padding: 12px 0; }}

    @media (max-width: 760px) {{
      .page {{ padding: 12px 10px 32px; }}
      #compare-chart {{ height: 320px; }}
    }}
  </style>
</head>
<body>
<div class="page">
  <div class="topbar">
    <div class="topbar-title">Compare Scenarios</div>
    <div class="topbar-sub">Net Worth Navigator</div>
    <a class="back-link" href="{shell_url}">← Back to projection</a>
  </div>

  <div class="controls">
    <div class="control-group">
      <div class="control-label">Scenarios</div>
      <div class="chip-row" id="scenario-chips"></div>
    </div>
    <div class="control-group">
      <div class="control-label">Mode</div>
      <select class="mode-select" id="mode-select">
        <option value="deterministic">Deterministic</option>
        <option value="historical">Historical</option>
        <option value="monte_carlo">Monte Carlo</option>
      </select>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Total Net Worth Trajectory</div>
    <div id="compare-chart"></div>
  </div>

  <div class="card">
    <div class="card-title">Scenario Metrics</div>
    <div class="kpi-table-wrap">
      <div id="kpi-area"><div class="loading-msg">Loading…</div></div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Investment Portfolio Trajectory <span style="font-weight:400;font-size:12px;color:var(--muted)">(excl. cash &amp; home equity)</span></div>
    <div id="portfolio-chart" style="width:100%;height:340px;"></div>
  </div>

  <div class="card">
    <div class="card-title">Annual Cash Flow <span style="font-weight:400;font-size:12px;color:var(--muted)">(income vs spending)</span></div>
    <div id="cashflow-chart" style="width:100%;height:320px;"></div>
    <div class="modeling-note" style="margin-top:6px"><strong>What this shows:</strong> Total household income (take-home + freed mortgage payments + events) vs total spending (living expenses + event outflows) for each year. Bars above zero are net surplus; below zero are net deficit funded by portfolio withdrawals.</div>
  </div>

  <div class="card">
    <div class="card-title">Net Worth Delta vs Baseline <span style="font-weight:400;font-size:12px;color:var(--muted)">(scenario − default)</span></div>
    <div id="delta-chart" style="width:100%;height:300px;"></div>
  </div>
</div>

<script>
(function() {{
  const MANIFEST = {inline_manifest};
  const COLORS = {colors_js};
  const SCENARIO_LIST = Array.isArray(MANIFEST.scenarios) ? MANIFEST.scenarios : [];
  const DEFAULT_SLUG = MANIFEST.default_slug || (SCENARIO_LIST[0] && SCENARIO_LIST[0].slug);

  // Assign stable colour index per scenario slug (by manifest order)
  const COLOR_MAP = {{}};
  SCENARIO_LIST.forEach(function(s, i) {{
    COLOR_MAP[s.slug] = COLORS[i % COLORS.length];
  }});

  // ── State ────────────────────────────────────────────────────────
  let activeMode = 'deterministic';
  let activeSlugs = new Set();

  // Boot selection: honour ?a=slug&b=slug URL params, else default + first other
  (function initSelection() {{
    const params = new URLSearchParams(window.location.search);
    const paramA = params.get('a');
    const paramB = params.get('b');
    const validSlugs = new Set(SCENARIO_LIST.map(s => s.slug));
    if (paramA && validSlugs.has(paramA)) activeSlugs.add(paramA);
    if (paramB && validSlugs.has(paramB)) activeSlugs.add(paramB);
    if (activeSlugs.size === 0) {{
      if (DEFAULT_SLUG) activeSlugs.add(DEFAULT_SLUG);
      const others = SCENARIO_LIST.filter(s => s.slug !== DEFAULT_SLUG);
      if (others.length) activeSlugs.add(others[0].slug);
    }}
    // If only one valid param was given, add the default as the second
    if (activeSlugs.size === 1 && DEFAULT_SLUG && !activeSlugs.has(DEFAULT_SLUG)) {{
      activeSlugs.add(DEFAULT_SLUG);
    }}
  }})();

  // ── Chip rendering ───────────────────────────────────────────────
  function renderChips() {{
    const row = document.getElementById('scenario-chips');
    row.innerHTML = '';
    SCENARIO_LIST.forEach(function(s) {{
      const color = COLOR_MAP[s.slug];
      const active = activeSlugs.has(s.slug);
      const chip = document.createElement('div');
      chip.className = 'chip' + (active ? ' active' : '');
      if (active) {{
        chip.style.backgroundColor = color;
        chip.style.borderColor = color;
      }} else {{
        chip.style.borderColor = color + '55';
      }}
      chip.innerHTML =
        '<span class="chip-dot" style="background:' + color + '"></span>' +
        s.name +
        (s.slug === DEFAULT_SLUG ? '<span style="font-size:10px;opacity:.7"> ★</span>' : '');
      chip.addEventListener('click', function() {{
        if (activeSlugs.has(s.slug)) {{
          if (activeSlugs.size <= 2) return; // keep at least 2
          activeSlugs.delete(s.slug);
        }} else {{
          activeSlugs.add(s.slug);
        }}
        renderChips();
        refresh();
      }});
      row.appendChild(chip);
    }});
  }}

  // ── Sidecar path helpers ─────────────────────────────────────────
  function sidecarBase(slug, mode) {{
    return 'scenarios/' + slug + '/' + mode + '/sidecars/';
  }}

  // ── CSV line parser (handles quoted fields) ───────────────────────
  function parseCSVLine(line) {{
    const result = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {{
      const ch = line[i];
      if (ch === '"') {{
        if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {{
          current += '"';
          i++;
        }} else {{
          inQuotes = !inQuotes;
        }}
      }} else if (ch === ',' && !inQuotes) {{
        result.push(current.trim());
        current = '';
      }} else {{
        current += ch;
      }}
    }}
    result.push(current.trim());
    return result;
  }}

  // ── CSV fetch helper ─────────────────────────────────────────────
  function parseCSV(text) {{
    const lines = text.trim().split('\\n');
    if (!lines.length) return [];
    const headers = parseCSVLine(lines[0]);
    return lines.slice(1).map(function(line) {{
      const vals = parseCSVLine(line);
      const obj = {{}};
      headers.forEach(function(h, i) {{ obj[h.trim()] = vals[i] !== undefined ? vals[i].trim() : ''; }});
      return obj;
    }});
  }}

  function fetchCSV(url) {{
    return fetch(url, {{ cache: 'no-cache' }}).then(function(r) {{
      if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + url);
      return r.text();
    }}).then(parseCSV);
  }}

  function fetchJSON(url) {{
    return fetch(url, {{ cache: 'no-cache' }}).then(function(r) {{
      if (!r.ok) throw new Error('HTTP ' + r.status + ' for ' + url);
      return r.json();
    }});
  }}

  // ── Number formatters ────────────────────────────────────────────
  function fmtM(v) {{
    const n = parseFloat(v);
    if (isNaN(n)) return '—';
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(0) + 'K';
    return n.toFixed(0);
  }}
  function fmtPct(v) {{
    const n = parseFloat(v);
    if (isNaN(n)) return '—';
    return (n * 100).toFixed(1) + '%';
  }}
  function fmtYear(v) {{
    return v ? String(v) : '—';
  }}
  function deltaClass(diff, higherIsBetter) {{
    if (diff === null || diff === undefined) return 'delta-neu';
    if (Math.abs(diff) < 0.0001) return 'delta-neu';
    return (diff > 0) === higherIsBetter ? 'delta-pos' : 'delta-neg';
  }}
  function fmtDelta(diff, fmt) {{
    if (diff === null || diff === undefined) return '';
    if (Math.abs(diff) < 1) return '';
    const sign = diff > 0 ? '+' : '';
    return ' <span style="font-size:11px;opacity:.75">(' + sign + fmt(diff) + ')</span>';
  }}

  // ── Main refresh ─────────────────────────────────────────────────
  function refresh() {{
    const slugs = Array.from(activeSlugs);
    if (!slugs.length) return;

    // Build sidecar fetch promises for each active scenario
    const projPromises = slugs.map(function(slug) {{
      const url = sidecarBase(slug, activeMode) + 'projection_yearly.csv';
      return fetchCSV(url).then(function(rows) {{ return {{ slug, rows }}; }}).catch(function() {{ return {{ slug, rows: null }}; }});
    }});
    const summPromises = slugs.map(function(slug) {{
      const url = sidecarBase(slug, activeMode) + 'simulation_summary.json';
      return fetchJSON(url).then(function(data) {{ return {{ slug, data }}; }}).catch(function() {{ return {{ slug, data: null }}; }});
    }});

    Promise.all([...projPromises, ...summPromises]).then(function(results) {{
      const projMap = {{}};
      const summMap = {{}};
      results.forEach(function(r) {{
        if (r.rows !== undefined) projMap[r.slug] = r.rows;
        if (r.data !== undefined) summMap[r.slug] = r.data;
      }});
      renderChart(slugs, projMap);
      renderPortfolioChart(slugs, projMap);
      renderCashFlowChart(slugs, projMap);
      renderDeltaChart(slugs, projMap);
      renderKPI(slugs, projMap, summMap);
    }});
  }}

  // ── Trajectory chart ─────────────────────────────────────────────
  function renderChart(slugs, projMap) {{
    const traces = [];
    slugs.forEach(function(slug) {{
      const rows = projMap[slug];
      if (!rows || !rows.length) return;
      const scenMeta = SCENARIO_LIST.find(s => s.slug === slug);
      const name = scenMeta ? scenMeta.name : slug;
      const color = COLOR_MAP[slug];
      const years = rows.map(r => parseInt(r.year));
      const vals  = rows.map(r => parseFloat(r.total_net_worth) / 1e6);
      traces.push({{
        x: years, y: vals, mode: 'lines', name: name,
        line: {{ color: color, width: slug === DEFAULT_SLUG ? 2.5 : 2 }},
        hovertemplate: '<b>%{{x}}</b><br>' + name + ': $%{{y:.2f}}M<extra></extra>',
      }});
    }});

    const layout = {{
      font: {{ color: '#e5edf7' }},
      paper_bgcolor: '#111827',
      plot_bgcolor: '#0f1725',
      xaxis: {{ title: 'Year', dtick: 2, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickfont: {{ size: 11 }} }},
      yaxis: {{ title: {{ text: 'Total Net Worth ($M)', standoff: 8 }}, automargin: true, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickformat: '$.2f', ticksuffix: 'M', tickfont: {{ size: 11 }} }},
      legend: {{ orientation: 'h', x: 0.5, xanchor: 'center', y: 1.02, yanchor: 'bottom', font: {{ size: 11 }} }},
      hoverlabel: {{ bgcolor: '#1e293b', bordercolor: '#7dd3fc', font_color: '#f8fafc' }},
      margin: {{ l: 80, r: 16, t: 48, b: 48 }},
    }};
    const el = document.getElementById('compare-chart');
    if (!el) return;
    if (el._hasPlot) {{
      Plotly.react(el, traces, layout);
    }} else {{
      Plotly.newPlot(el, traces, layout, {{ responsive: true, displayModeBar: false }});
      el._hasPlot = true;
    }}
  }}

  // ── Portfolio chart ───────────────────────────────────────────────
  function renderPortfolioChart(slugs, projMap) {{
    const traces = [];
    slugs.forEach(function(slug) {{
      const rows = projMap[slug];
      if (!rows || !rows.length) return;
      const scenMeta = SCENARIO_LIST.find(s => s.slug === slug);
      const name = scenMeta ? scenMeta.name : slug;
      const color = COLOR_MAP[slug];
      const years = rows.map(r => parseInt(r.year));
      const vals = rows.map(function(r) {{
        const t  = parseFloat(r.taxable)  || 0;
        const tr = parseFloat(r.trad_ira) || 0;
        const ro = parseFloat(r.roth)     || 0;
        return (t + tr + ro) / 1e6;
      }});
      traces.push({{
        x: years, y: vals, mode: 'lines', name: name,
        line: {{ color: color, width: slug === DEFAULT_SLUG ? 2.5 : 2, dash: slug === DEFAULT_SLUG ? 'solid' : 'dot' }},
        hovertemplate: '<b>%{{x}}</b><br>' + name + ': $%{{y:.2f}}M<extra></extra>',
      }});
    }});

    const layout = {{
      font: {{ color: '#e5edf7' }},
      paper_bgcolor: '#111827',
      plot_bgcolor: '#0f1725',
      xaxis: {{ title: 'Year', dtick: 2, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickfont: {{ size: 11 }} }},
      yaxis: {{ title: {{ text: 'Account Balance ($M)', standoff: 8 }}, automargin: true, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickformat: '$.2f', ticksuffix: 'M', tickfont: {{ size: 11 }} }},
      legend: {{ orientation: 'h', x: 0.5, xanchor: 'center', y: 1.02, yanchor: 'bottom', font: {{ size: 11 }} }},
      hoverlabel: {{ bgcolor: '#1e293b', bordercolor: '#7dd3fc', font_color: '#f8fafc' }},
      margin: {{ l: 80, r: 16, t: 48, b: 48 }},
    }};
    const el = document.getElementById('portfolio-chart');
    if (!el) return;
    if (el._hasPlot) {{
      Plotly.react(el, traces, layout);
    }} else {{
      Plotly.newPlot(el, traces, layout, {{ responsive: true, displayModeBar: false }});
      el._hasPlot = true;
    }}
  }}

  // ── Annual Cash Flow chart ────────────────────────────────────────
  function renderCashFlowChart(slugs, projMap) {{
    const traces = [];
    slugs.forEach(function(slug) {{
      const rows = projMap[slug];
      if (!rows || !rows.length) return;
      const scenMeta = SCENARIO_LIST.find(s => s.slug === slug);
      const name = scenMeta ? scenMeta.name : slug;
      const color = COLOR_MAP[slug];
      const years = rows.map(r => parseInt(r.year));

      // Income = person1 + person2 take-home + freed_payments
      const income = rows.map(function(r) {{
        const p1 = parseFloat(r.person1_income) || 0;
        const p2 = parseFloat(r.person2_income) || 0;
        const fr = parseFloat(r.freed_payments) || 0;
        return (p1 + p2 + fr) / 1e6;
      }});

      // Spend = annual_spend (already negative in model; flip to positive for display)
      const spend = rows.map(r => Math.abs(parseFloat(r.annual_spend) || 0) / 1e6);

      // Net = income - spend (positive = surplus, negative = deficit)
      const net = income.map((inc, i) => inc - spend[i]);

      const isDash = slug !== DEFAULT_SLUG;

      traces.push({{
        x: years, y: income, mode: 'lines', name: name + ' income',
        line: {{ color: color, width: 1.6, dash: isDash ? 'dot' : 'solid' }},
        hovertemplate: '<b>%{{x}}</b><br>' + name + ' income: %{{y:$,.3f}}M<extra></extra>',
      }});
      traces.push({{
        x: years, y: spend, mode: 'lines', name: name + ' spending',
        line: {{ color: color, width: 1.6, dash: isDash ? 'longdash' : 'dash' }},
        opacity: 0.65,
        hovertemplate: '<b>%{{x}}</b><br>' + name + ' spending: %{{y:$,.3f}}M<extra></extra>',
      }});
      traces.push({{
        x: years, y: net, mode: 'lines', name: name + ' net',
        fill: 'tozeroy',
        fillcolor: color.replace('rgb', 'rgba').replace(')', ',0.12)').replace('#', 'rgba(').replace(/rgba\(([0-9a-f]{{2}})([0-9a-f]{{2}})([0-9a-f]{{2}}),0\.12\)/, function(_, r, g, b) {{
          return 'rgba(' + parseInt(r, 16) + ',' + parseInt(g, 16) + ',' + parseInt(b, 16) + ',0.12)';
        }}),
        line: {{ color: color, width: 2.2, dash: isDash ? 'dashdot' : 'solid' }},
        hovertemplate: '<b>%{{x}}</b><br>' + name + ' net flow: %{{y:$,.3f}}M<extra></extra>',
      }});
    }});

    const layout = {{
      font: {{ color: '#e5edf7' }},
      paper_bgcolor: '#111827',
      plot_bgcolor: '#0f1725',
      xaxis: {{ title: 'Year', dtick: 2, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickfont: {{ size: 11 }} }},
      yaxis: {{ title: {{ text: 'Annual ($M)', standoff: 8 }}, automargin: true, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickformat: '$.2f', ticksuffix: 'M', tickfont: {{ size: 11 }}, zeroline: true, zerolinecolor: 'rgba(148,163,184,0.35)', zerolinewidth: 1 }},
      legend: {{ orientation: 'h', x: 0.5, xanchor: 'center', y: 1.02, yanchor: 'bottom', font: {{ size: 10 }} }},
      hoverlabel: {{ bgcolor: '#1e293b', bordercolor: '#7dd3fc', font_color: '#f8fafc' }},
      margin: {{ l: 80, r: 16, t: 48, b: 48 }},
    }};
    const el = document.getElementById('cashflow-chart');
    if (!el) return;
    if (el._hasPlot) {{
      Plotly.react(el, traces, layout);
    }} else {{
      Plotly.newPlot(el, traces, layout, {{ responsive: true, displayModeBar: false }});
      el._hasPlot = true;
    }}
  }}

  // ── Delta chart (scenario − baseline) ───────────────────────────
  function renderDeltaChart(slugs, projMap) {{
    const baselineRows = projMap[DEFAULT_SLUG] || (slugs.length ? projMap[slugs[0]] : null);
    if (!baselineRows || !baselineRows.length) return;

    const baselineByYear = {{}};
    baselineRows.forEach(function(r) {{ baselineByYear[parseInt(r.year)] = parseFloat(r.total_net_worth); }});

    const traces = [];
    slugs.forEach(function(slug) {{
      const rows = projMap[slug];
      if (!rows || !rows.length) return;
      const scenMeta = SCENARIO_LIST.find(s => s.slug === slug);
      const name = scenMeta ? scenMeta.name : slug;
      const color = COLOR_MAP[slug];
      const years = rows.map(r => parseInt(r.year));
      const vals  = rows.map(function(r) {{
        const yr = parseInt(r.year);
        const base = baselineByYear[yr];
        if (base === undefined) return null;
        return (parseFloat(r.total_net_worth) - base) / 1e6;
      }});

      // Skip if this is the baseline itself (all zeros) or no non-null values
      const nonNull = vals.filter(v => v !== null);
      if (!nonNull.length) return;
      const allZero = nonNull.every(v => Math.abs(v) < 1e-6);
      if (allZero) return;  // don't draw the baseline − baseline = 0 line

      traces.push({{
        x: years, y: vals, mode: 'lines', name: name,
        line: {{ color: color, width: 2 }},
        hovertemplate: '<b>%{{x}}</b><br>' + name + ' delta: %{{y:+.2f}}M<extra></extra>',
      }});
    }});

    // Always draw a zero reference line
    const allYears = baselineRows.map(r => parseInt(r.year));
    traces.unshift({{
      x: [allYears[0], allYears[allYears.length - 1]], y: [0, 0],
      mode: 'lines', name: 'Baseline (default)', showlegend: true,
      line: {{ color: 'rgba(148,163,184,0.35)', width: 1, dash: 'dot' }},
      hoverinfo: 'skip',
    }});

    const layout = {{
      font: {{ color: '#e5edf7' }},
      paper_bgcolor: '#111827',
      plot_bgcolor: '#0f1725',
      xaxis: {{ title: {{ text: 'Year', standoff: 20 }}, dtick: 2, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickfont: {{ size: 11 }}, ticklabelstandoff: 16 }},
      yaxis: {{ title: {{ text: 'Δ Net Worth ($M)', standoff: 8 }}, automargin: true, gridcolor: 'rgba(148,163,184,.12)', color: '#e5edf7', tickformat: '+$.2f', ticksuffix: 'M', tickfont: {{ size: 11 }}, zeroline: false }},
      legend: {{ orientation: 'h', x: 0.5, xanchor: 'center', y: 1.02, yanchor: 'bottom', font: {{ size: 11 }} }},
      hoverlabel: {{ bgcolor: '#1e293b', bordercolor: '#7dd3fc', font_color: '#f8fafc' }},
      margin: {{ l: 100, r: 16, t: 48, b: 72 }},
    }};
    const el = document.getElementById('delta-chart');
    if (!el) return;
    if (el._hasPlot) {{
      Plotly.react(el, traces, layout);
    }} else {{
      Plotly.newPlot(el, traces, layout, {{ responsive: true, displayModeBar: false }});
      el._hasPlot = true;
    }}
  }}

  // ── KPI table ────────────────────────────────────────────────────
  function renderKPI(slugs, projMap, summMap) {{
    const kpiArea = document.getElementById('kpi-area');

    // Gather metrics per scenario
    const rows = slugs.map(function(slug) {{
      const proj = projMap[slug] || [];
      const summ = summMap[slug] || {{}};
      const meta = SCENARIO_LIST.find(s => s.slug === slug) || {{}};

      const lastRow = proj.length ? proj[proj.length - 1] : null;
      const retYear = parseInt(summ.retirement_year) || null;
      const retRow  = retYear ? proj.find(r => parseInt(r.year) === retYear) : null;

      return {{
        slug,
        name: meta.name || slug,
        isDefault: slug === DEFAULT_SLUG,
        termNW: lastRow ? parseFloat(lastRow.total_net_worth) : null,
        termInv: lastRow ? (parseFloat(lastRow.taxable || 0) + parseFloat(lastRow.trad_ira || 0) + parseFloat(lastRow.roth || 0)) : null,
        retNW: retRow ? parseFloat(retRow.total_net_worth) : null,
        retYear: retYear,
        successRate: summ.probability_of_success != null ? parseFloat(summ.probability_of_success) : null,
        termNWp10: summ.terminal_total_net_worth_p10 != null ? parseFloat(summ.terminal_total_net_worth_p10) : null,
        termNWp90: summ.terminal_total_net_worth_p90 != null ? parseFloat(summ.terminal_total_net_worth_p90) : null,
        worstDecile: summ.worst_decile_terminal_net_worth != null ? parseFloat(summ.worst_decile_terminal_net_worth) : null,
        firstFailP50: summ.first_failure_year_p50 || null,
        peakPressure: summ.peak_temporary_pressure_rate != null ? parseFloat(summ.peak_temporary_pressure_rate) : null,
      }};
    }});

    // Find baseline (default scenario or first in list)
    const baseline = rows.find(r => r.isDefault) || rows[0];

    // Determine whether MC metrics are available
    const hasMC = rows.some(r => r.successRate !== null);

    // Build table HTML
    const cols = [
      {{ key: 'name', label: 'Scenario', fmt: null, higherBetter: null }},
      {{ key: 'retYear', label: 'Retirement Year', fmt: fmtYear, higherBetter: false }},
      {{ key: 'retNW', label: 'NW at Retirement', fmt: fmtM, higherBetter: true }},
      {{ key: 'termNW', label: 'Terminal NW', fmt: fmtM, higherBetter: true }},
      {{ key: 'termInv', label: 'Terminal Investable', fmt: fmtM, higherBetter: true }},
    ];
    if (hasMC) {{
      cols.push({{ key: 'successRate', label: 'Prob. of Success', fmt: fmtPct, higherBetter: true }});
      cols.push({{ key: 'worstDecile', label: 'Worst-Decile Terminal', fmt: fmtM, higherBetter: true }});
      cols.push({{ key: 'termNWp10', label: 'Terminal P10', fmt: fmtM, higherBetter: true }});
      cols.push({{ key: 'termNWp90', label: 'Terminal P90', fmt: fmtM, higherBetter: true }});
      cols.push({{ key: 'firstFailP50', label: 'Median 1st Failure', fmt: fmtYear, higherBetter: true }});
      cols.push({{ key: 'peakPressure', label: 'Peak Pressure Rate', fmt: fmtPct, higherBetter: false }});
    }}

    let thead = '<tr>';
    cols.forEach(function(c) {{ thead += '<th>' + c.label + '</th>'; }});
    thead += '</tr>';

    let tbody = '';
    rows.forEach(function(row) {{
      const color = COLOR_MAP[row.slug];
      tbody += '<tr>';
      cols.forEach(function(c) {{
        if (c.key === 'name') {{
          tbody += '<td class="kpi-name"><span class="kpi-swatch" style="background:' + color + '"></span>' + row.name;
          if (row.isDefault) tbody += '<span class="kpi-default-marker">★</span>';
          tbody += '</td>';
          return;
        }}
        const val = row[c.key];
        const bval = baseline ? baseline[c.key] : null;
        const fval = val !== null && val !== undefined && c.fmt ? c.fmt(val) : (val !== null && val !== undefined ? String(val) : '—');
        let deltaHtml = '';
        if (!row.isDefault && bval !== null && val !== null && c.fmt === fmtM) {{
          const diff = val - bval;
          const dc = deltaClass(diff, c.higherBetter);
          deltaHtml = '<span class="' + dc + '">' + fmtDelta(diff, fmtM) + '</span>';
        }} else if (!row.isDefault && bval !== null && val !== null && c.fmt === fmtPct) {{
          const diff = val - bval;
          const dc = deltaClass(diff, c.higherBetter);
          if (Math.abs(diff) > 0.0005) {{
            const sign = diff > 0 ? '+' : '';
            deltaHtml = ' <span class="' + dc + '" style="font-size:11px;opacity:.75">(' + sign + fmtPct(diff) + ')</span>';
          }}
        }} else if (!row.isDefault && bval !== null && val !== null && c.fmt === fmtYear) {{
          const diff = parseInt(val) - parseInt(bval);
          if (!isNaN(diff) && diff !== 0) {{
            const dc = deltaClass(diff, c.higherBetter);
            const sign = diff > 0 ? '+' : '';
            deltaHtml = ' <span class="' + dc + '" style="font-size:11px;opacity:.75">(' + sign + diff + 'yr)</span>';
          }}
        }}
        tbody += '<td class="kpi-num">' + fval + deltaHtml + '</td>';
      }});
      tbody += '</tr>';
    }});

    kpiArea.innerHTML = (
      '<table class="kpi"><thead>' + thead + '</thead><tbody>' + tbody + '</tbody></table>'
    );
  }}

  // ── Mode selector ─────────────────────────────────────────────────
  function resolveAvailableModes() {{
    const allModes = new Set();
    SCENARIO_LIST.forEach(function(s) {{
      if (Array.isArray(s.modes)) {{
        s.modes.forEach(function(m) {{ allModes.add(m.mode); }});
      }}
    }});
    const sel = document.getElementById('mode-select');
    Array.from(sel.options).forEach(function(opt) {{
      opt.disabled = !allModes.has(opt.value);
    }});
  }}

  // ── Boot ─────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function() {{
    resolveAvailableModes();
    document.getElementById('mode-select').addEventListener('change', function() {{
      activeMode = this.value;
      refresh();
    }});
    renderChips();
    refresh();
  }});
}})();
</script>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(compare_html, encoding="utf-8")