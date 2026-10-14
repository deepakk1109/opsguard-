# One-time setup (run from the repo root in PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Write-Host "Setup done. Next: .\scripts\start_decider.ps1 (in a second terminal)"
