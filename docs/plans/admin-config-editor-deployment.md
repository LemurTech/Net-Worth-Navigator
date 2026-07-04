# Admin Config Editor Deployment

## Purpose

This project now includes a small web admin page for editing `config.toml` directly from the browser.

Public URL:
- `http://casalemuria.lan/finances/config/`

Projection page:
- `http://casalemuria.lan/finances/projection.html`

## Application

Repo files:
- `admin_app.py` — FastAPI app
- `templates/config_editor.html` — HTML template
- `Dockerfile.config-editor` — lightweight runtime image for the editor backend

Key behaviors:
- loads the current `config.toml`
- validates TOML before save
- writes timestamped backups to `output/config-backups/`
- supports `Save + Re-render`, which runs `python run.py --offline`

## Serving model

The static chart page is still served by the existing `hal-pages` nginx container.
The config editor is a separate backend process proxied by nginx.

Operational files outside the repo:
- `/opt/hal-pages/docker-compose.yml`
- `/opt/hal-pages/default.conf`

Expected nginx route:
- `/finances/config/` → proxied to `nwn-config-editor:8010`

Expected Compose service:
- `nwn-config-editor` built from this repo's `Dockerfile.config-editor`

## Verification

Host checks:

```bash
curl http://127.0.0.1/finances/config/
curl http://127.0.0.1/finances/projection.html | grep 'Edit Config'
```

Container checks:

```bash
docker ps | grep -E 'hal-pages|nwn-config-editor'
docker logs --tail 50 nwn-config-editor
```

Functional test:
1. Open `/finances/config/`
2. Click `Validate`
3. Click `Save + Re-render`
4. Confirm success banner and backup path
5. Open `projection.html` and confirm the chart still renders

## Known limitation

This is intentionally a raw TOML editor, not a structured form editor.
That keeps comment preservation and schema flexibility simple for V1.
