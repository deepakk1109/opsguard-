# WSL + free local Kubernetes (kind) instead of OpenShift

OpsGuard accepts both `oc` and `kubectl`. kind = Kubernetes inside Docker: free, no expiry,
anyone (including judges) can reproduce your demo.

All commands below run inside WSL (Ubuntu). Work in the Linux home folder (~), NOT /mnt/c (slow).

## 1. Get the project into WSL
```bash
cp /mnt/c/Users/<WindowsUser>/Downloads/opsguard.zip ~ && cd ~ && sudo apt update && sudo apt install -y unzip git curl python3-venv
unzip opsguard.zip && cd opsguard
python3 --version        # 3.10+ needed, 3.12 best
```

## 2. Python env + tests (no model, no AWS)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -t .
```

## 3. Decider server (terminal 2)
```bash
cd ~/opsguard && source .venv/bin/activate
strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --port 8099
```
First run downloads ~9 GB. WSL usually has no GPU, so it runs on CPU: slower than the 115 ms
published for an RTX 3090. Report YOUR measured numbers.

## 4. AWS CLI + Bedrock
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip && unzip -q awscliv2.zip && sudo ./aws/install
aws configure            # IAM user access key (never the root account), region us-east-1
aws sts get-caller-identity
```
Bedrock console (us-east-1): enable Claude Haiku 4.5. Set a Budget alert in AWS Billing.

## 5. Docker + kubectl + kind
Easiest: Docker Desktop on Windows -> Settings -> Resources -> WSL integration -> enable for your Ubuntu.
Then in WSL: `docker ps` must work.
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64 && sudo install kind /usr/local/bin/kind
kind create cluster --name opsguard
kubectl get nodes
```

## 6. Demo workloads
```bash
kubectl create namespace dev
kubectl create namespace payments-prod
kubectl create deployment payments --image=nginx --replicas=2 -n dev
kubectl create deployment payments --image=nginx --replicas=2 -n payments-prod
kubectl get pods -A
```

## 7. Run
```bash
export OPSGUARD_CLI=kubectl
export OPSGUARD_DRY_RUN=0          # 1 = simulate only
python agent.py
```
Try: "list pods in dev" -> "restart the payments deployment in dev" ->
"delete pod <real-pod-name> in dev" -> "yes" -> "scale payments in payments-prod to zero" (denied).
Pod names come from `kubectl get pods -n dev`.
