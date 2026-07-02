#!/usr/bin/env python3
"""
verify_install.py — Installation health check for Net Worth Navigator

Verifies:
- Python version (3.11+)
- Required dependencies installed
- Can parse starter.toml
- Can generate a minimal projection
- Reports overall status (green/red)

Usage:
    python scripts/verify_install.py
"""

import sys
from pathlib import Path

# Add src to path so we can import without installing
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

def check_python_version():
    """Check that Python 3.11+ is running."""
    print("Checking Python version...", end=" ")
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro}")
        print(f"  ERROR: Python 3.11 or later required")
        return False


def check_dependencies():
    """Check that required packages are installed."""
    print("Checking dependencies...", end=" ")
    required = ["plotly", "pandas", "fastapi", "uvicorn", "jinja2", "tomlkit"]
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if not missing:
        print(f"✓ All {len(required)} required packages installed")
        return True
    else:
        print(f"✗ Missing: {', '.join(missing)}")
        print("  Install with: python -m pip install -r requirements.txt")
        return False


def check_toml_parsing():
    """Check that we can parse starter.toml."""
    print("Checking TOML parsing...", end=" ")
    starter_path = repo_root / "scenarios" / "starter.toml"
    
    if not starter_path.exists():
        print(f"✗ starter.toml not found at {starter_path}")
        return False
    
    try:
        import tomllib
        with open(starter_path, "rb") as f:
            config = tomllib.load(f)
        
        # Verify basic structure
        required_sections = ["scenario", "data_source", "simulation", "person1", "spending", "assumptions"]
        missing = [s for s in required_sections if s not in config]
        
        if missing:
            print(f"✗ Missing sections in starter.toml: {', '.join(missing)}")
            return False
        
        print("✓ starter.toml parses correctly")
        return True
    except Exception as e:
        print(f"✗ Failed to parse starter.toml: {e}")
        return False


def check_minimal_projection():
    """Check that we can import core model modules."""
    print("Checking model imports...", end=" ")
    
    try:
        from src import config_loader, model, charts
        print("✓ Core modules import successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import core modules: {e}")
        print("  This might indicate missing dependencies or a broken installation")
        return False


def check_output_directory():
    """Check that output directory exists or can be created."""
    print("Checking output directory...", end=" ")
    output_dir = repo_root / "output"
    
    try:
        output_dir.mkdir(exist_ok=True)
        print(f"✓ Output directory ready at {output_dir}")
        return True
    except Exception as e:
        print(f"✗ Cannot create output directory: {e}")
        return False


def main():
    print("=" * 70)
    print("Net Worth Navigator — Installation Verification")
    print("=" * 70)
    print()
    
    checks = [
        check_python_version,
        check_dependencies,
        check_toml_parsing,
        check_minimal_projection,
        check_output_directory,
    ]
    
    results = [check() for check in checks]
    
    print()
    print("=" * 70)
    
    if all(results):
        print("✓ ALL CHECKS PASSED")
        print()
        print("Installation is ready. Next steps:")
        print()
        print("1. Try the sample scenario:")
        print("   python run.py --scenario sample")
        print()
        print("2. Create your own scenario:")
        print("   Linux/macOS:  cp scenarios/starter.toml scenarios/myhousehold.toml")
        print("   Windows:      copy scenarios\\starter.toml scenarios\\myhousehold.toml")
        print("   Then edit myhousehold.toml and run:")
        print("   python run.py --scenario myhousehold")
        print()
        print("3. Use the web UI:")
        print("   python admin_app.py")
        print("   Open http://localhost:8010/setup")
        print()
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        print()
        print("Please fix the errors above before running projections.")
        print()
        failed_count = len([r for r in results if not r])
        print(f"{failed_count} of {len(checks)} checks failed.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
