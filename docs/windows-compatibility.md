# Windows Compatibility Guide

Net Worth Navigator is cross-platform and runs on Windows, macOS, and Linux. This guide covers Windows-specific setup and usage patterns.

## Key Differences from Linux/macOS

| Aspect | Linux/macOS | Windows |
|--------|-------------|---------|
| Python venv activation | `.venv/bin/python` | `.venv\Scripts\python.exe` |
| Path separators | `/` (forward slash) | `\` (backslash) |
| Copy command | `cp` | `copy` |
| Text editor (basic) | `nano` | `notepad` |
| Open file command | `open` | `start` |

## Installation

```powershell
# Clone the repository
git clone https://github.com/YourOrg/Net-Worth-Navigator.git
cd Net-Worth-Navigator

# Create virtual environment
python -m venv .venv

# Install dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Running Without Monarch (Recommended for First-Time Windows Users)

```powershell
# 1. Copy the starter template
copy scenarios\starter.toml scenarios\myhousehold.toml

# 2. Edit with your data
notepad scenarios\myhousehold.toml

# 3. Run the projection
.venv\Scripts\python.exe run.py --scenario myhousehold

# 4. View output
start output\projection.html
```

## Running With Monarch (Advanced)

If you have Monarch Money and want to use live account balances:

### Step 1: Install Monarch MCP Server

Follow the [Monarch MCP setup guide](https://github.com/Agentic-Insights/monarch-mcp) to install the Monarch MCP server on Windows. Typical installation path: `C:\Users\YourName\monarch-mcp-server`

### Step 2: Configure the Path

Set the `MONARCH_MCP_PATH` environment variable to point to your MCP installation:

**PowerShell (current session only):**
```powershell
$env:MONARCH_MCP_PATH = "C:\Users\YourName\monarch-mcp-server"
```

**Persistent (system-wide):**
1. Open System Properties → Environment Variables
2. Add a new user variable:
   - Name: `MONARCH_MCP_PATH`
   - Value: `C:\Users\YourName\monarch-mcp-server`

### Step 3: Run with Monarch

```powershell
# Full run (pulls live balances)
.venv\Scripts\python.exe run.py

# Offline mode (uses cached balances)
.venv\Scripts\python.exe run.py --offline
```

## Path Handling

Net Worth Navigator uses Python's `pathlib.Path`, which automatically handles cross-platform path separators. When writing TOML config or command-line paths:

- **In TOML files:** Use forward slashes `/` — Python converts them automatically
- **In PowerShell/cmd:** Use backslashes `\` for file paths
- **In documentation examples:** This guide shows both formats where relevant

## Common Windows Issues

### Issue: "python is not recognized"

**Solution:** Ensure Python is installed and added to your PATH. Download from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH" during installation.

### Issue: "No module named 'some_package'"

**Solution:** Activate the venv and reinstall dependencies:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Issue: "Monarch MCP server not found"

**Solution (if using synthetic mode):** This is expected — synthetic mode doesn't need Monarch. Ignore the warning.

**Solution (if using Monarch):** Set the `MONARCH_MCP_PATH` environment variable as described above.

### Issue: Output files don't render correctly

**Solution:** Use a modern browser (Chrome, Edge, Firefox). Internet Explorer is not supported.

## Performance Notes

Windows file I/O is typically slower than Linux for operations that create many small files (e.g., generating backup TOML files). This is normal and does not affect the accuracy of projections. For large scenario sets, consider:

- Running on WSL2 (Windows Subsystem for Linux) for better performance
- Using the web UI for editing instead of frequent file copies
- Keeping fewer backup files (adjust retention in `admin_app.py` if needed)

## WSL2 Option

For advanced users, you can run Net Worth Navigator inside WSL2 and get native Linux performance:

```bash
# Inside WSL2 Ubuntu
cd /mnt/c/Users/YourName/Net-Worth-Navigator
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py --scenario myhousehold
```

Then access the output via Windows file explorer at `\\wsl$\Ubuntu\home\...` or set up a shared mount point.

## Web UI / Config Editor on Windows

The FastAPI-based config editor works identically on Windows:

```powershell
# Start the config editor server
.venv\Scripts\python.exe admin_app.py

# Open in browser
start http://localhost:8010/setup
```

**Note:** The nginx deployment pattern shown in the main README is Linux-specific. Windows users should use the built-in FastAPI dev server (shown above) or deploy via IIS/nginx for Windows if production hosting is needed.

## Troubleshooting

If you encounter issues not covered here:

1. Check that you're using Python 3.11 or later: `.venv\Scripts\python.exe --version`
2. Verify dependencies installed: `.venv\Scripts\python.exe -m pip list`
3. Run with verbose output: `.venv\Scripts\python.exe run.py --scenario <slug> 2>&1 | Out-File debug.log`
4. Check the log file for specific errors

## Testing on Windows

The full test suite runs on Windows with pytest:

```powershell
.venv\Scripts\python.exe -m pip install pytest pytest-xdist
.venv\Scripts\python.exe -m pytest tests/ -v
```

**Known test skips:** Some integration tests that assume Unix-style paths may be skipped on Windows. This is expected and does not affect production usage.
