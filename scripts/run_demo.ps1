# Terminal 1: scripted demo in DRY-RUN mode (nothing is executed)
.\.venv\Scripts\Activate.ps1
$env:OPSGUARD_DRY_RUN = "1"
python agent.py --demo
