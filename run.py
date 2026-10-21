
import sys
import subprocess
import os

REQUIRED_PYTHON   = (3, 9)
REQUIRED_PACKAGES = ["yfinance","pandas","streamlit","plotly","groq","ta","numpy"]
REQUIRED_FILES    = ["app.py","fetcher.py","cleaner.py","metrics.py",
                     "scorer.py","ai_summary.py","config.py",
                     "cache.py","logger.py","validator.py"]


def step(n, total, msg):
    print(f"  [{n}/{total}] {msg}", end=" ", flush=True)

def ok(detail=""):
    print(f"✓  {detail}")

def fail(msg):
    print(f"✗\n\n  ERROR: {msg}\n")
    sys.exit(1)

# ── 1. Python version ──
step(1, 4, "Python version ........")
v = sys.version_info
if v < REQUIRED_PYTHON:
    fail(f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required. You have {v.major}.{v.minor}.")
ok(f"Python {v.major}.{v.minor}.{v.micro}")

# ── 2. Packages ──
step(2, 4, "Dependencies .......... ")
missing = []
for pkg in REQUIRED_PACKAGES:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f"\n        Installing: {', '.join(missing)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
        print("        ", end="")
        ok("Installed successfully")
    except subprocess.CalledProcessError:
        fail(f"Could not install: {', '.join(missing)}\nRun manually: pip install {' '.join(missing)}")
else:
    ok("All packages present")

# ── 3. Project files ──
step(3, 4, "Project files ......... ")
script_dir = os.path.dirname(os.path.abspath(__file__))
missing_files = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(script_dir, f))]
if missing_files:
    fail(f"Missing files: {', '.join(missing_files)}\nEnsure all files are in the same folder as run.py.")
ok(f"{len(REQUIRED_FILES)} files verified")

# ── 4. Config check ──
step(4, 4, "Config validation ..... ")
sys.path.insert(0, script_dir)
try:
    import config
    key_set = config.GROQ_API_KEY not in ("", "your_groq_api_key_here")
    weights_sum = sum(config.METRIC_WEIGHTS.values())
    if abs(weights_sum - 1.0) > 0.01:
        fail(f"METRIC_WEIGHTS in config.py must sum to 1.0 (currently {weights_sum:.2f})")
    ok(f"Groq API {'configured ✓' if key_set else 'not set (fallback mode)'}")
except Exception as e:
    fail(f"config.py error: {e}")

# ── Launch ──
print()
print("  ► Dashboard: http://localhost:8501")
print("  ► Logs:      finsight.log")
print("  ► Stop:      Ctrl+C")
print()
print("=" * 60)

app_path = os.path.join(script_dir, "app.py")
try:
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", app_path,
        "--server.headless",              "false",
        "--browser.gatherUsageStats",     "false",
        "--theme.base",                   "dark",
        "--theme.backgroundColor",        "#111827",
        "--theme.secondaryBackgroundColor","#1e293b",
        "--theme.textColor",              "#e2e8f0",
        "--theme.primaryColor",           "#3b82f6",
    ])
except KeyboardInterrupt:
    print("\n\n  FinSight stopped.\n")
except FileNotFoundError:
    fail(f"Streamlit not found. Run: pip install streamlit\nThen: streamlit run {app_path}")
