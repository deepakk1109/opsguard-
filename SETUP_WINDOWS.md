# Windows setup, step by step

All commands are PowerShell. Run them from the repo folder.

## 0. One-time installs (winget)
```powershell
winget install Python.Python.3.12
winget install Git.Git
winget install Amazon.AWSCLI
```
Close and reopen PowerShell afterwards. Check: `python --version`, `git --version`, `aws --version`.
Install the OpenShift CLI (`oc`) from your cluster web console (? icon -> Command line tools) and add it to PATH.

If scripts are blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 1. Python environment
```powershell
.\scripts\setup.ps1
```

## 2. Start Decider (Terminal 2, leave open)
```powershell
.\scripts\start_decider.ps1
```
First run downloads ~9 GB. Wait for the "Uvicorn running on port 8099" line.
If v21 misbehaves: `$env:DECIDER_MODEL="StrandsAgents/strands-decider-2B-hobson-v19"` then start again.
If it will not run natively on Windows, use WSL2 (Ubuntu) with the same steps (Linux commands).

## 3. AWS + Bedrock
```powershell
aws login            # or: aws configure
aws sts get-caller-identity
```
In the Bedrock console (region us-east-1) make sure Claude Haiku 4.5 is available to your account.

## 4. Run
```powershell
.\scripts\run_demo.ps1
python bench.py --llm
```

## 5. Real OpenShift
```powershell
oc login --token=... --server=...      # copy from the console
$env:OPSGUARD_DRY_RUN = "0"
python agent.py
```
Use a sandbox project. Create a throwaway `payments` deployment in `dev` and a `payments-prod` namespace to demo Confirm/Deny safely.

## 6. Push to GitHub
1. github.com -> New repository -> name `opsguard` -> Public -> do NOT add README/.gitignore -> Create.
2. In the repo folder:
```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git init
git add .
git commit -m "OpsGuard: Decider-gated OpenShift agent"
git branch -M main
git remote add origin https://github.com/<your-username>/opsguard.git
git push -u origin main
```
A browser window opens for GitHub sign-in the first time.
