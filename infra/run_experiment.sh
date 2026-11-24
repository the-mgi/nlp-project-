#!/usr/bin/env bash
# ONE MASTER SCRIPT (run on your laptop):
#   provision the cluster -> run the experiment on it -> download the results -> optionally destroy.
#
#   SSH_KEY=~/.ssh/id_ed25519 DESTROY=1 bash infra/run_experiment.sh
#
# Requirements: terraform >= 1.5, AWS credentials (aws configure or env vars),
# infra/terraform/terraform.tfvars (copy terraform.tfvars.example and set allowed_ssh_cidr).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}
OUT=${OUT:-$HERE/../experiment-results}
DESTROY=${DESTROY:-0}
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30"

cd "$HERE/terraform"
terraform init -input=false
terraform apply -auto-approve -input=false
MASTER=$(terraform output -raw master_public_ip)
echo "master: $MASTER   workers: $(terraform output -json worker_private_ips)"

echo "waiting for the master bootstrap (packages, LaTeX, models, sources)..."
until $SSH ubuntu@"$MASTER" "test -f /var/lib/rjb-bootstrap-done" 2> /dev/null; do sleep 30; done

# run the orchestrator detached on the master so a dropped laptop connection does not stop it
$SSH ubuntu@"$MASTER" "tmux new-session -d -s rjb 'bash ~/nlp-project-/infra/scripts/orchestrate.sh 2>&1 | tee ~/orchestrate.log'"
echo "experiment running; follow it with:  $SSH ubuntu@$MASTER tail -f orchestrate.log"
until $SSH ubuntu@"$MASTER" "grep -q 'EXPERIMENT DONE' ~/orchestrate.log" 2> /dev/null; do sleep 120; done

mkdir -p "$OUT"
scp -i "$SSH_KEY" ubuntu@"$MASTER":rjb-results.tgz "$OUT/"
tar xzf "$OUT/rjb-results.tgz" -C "$OUT"
echo "results in $OUT"

if [ "$DESTROY" = "1" ]; then
  terraform destroy -auto-approve -input=false
fi
