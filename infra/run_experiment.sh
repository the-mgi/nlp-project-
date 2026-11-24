#!/usr/bin/env bash
# ONE MASTER SCRIPT (run on the operator machine):
#   check the AWS account -> provision the cluster -> run the experiment on it
#   -> download the results -> optionally destroy everything.
#
#   DESTROY=1 bash infra/run_experiment.sh
#
# Requirements: terraform >= 1.5, AWS CLI v2 with credentials for account 602170263568.
# Settings: infra/terraform/terraform.tfvars
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ACCOUNT_ID=602170263568
SSH_KEY=${SSH_KEY:-$HOME/.ssh/id_ed25519}
OUT=${OUT:-$HERE/../experiment-results}
DESTROY=${DESTROY:-0}

# 1. credentials must belong to the expected account
CALLER=$(aws sts get-caller-identity --query Account --output text)
if [ "$CALLER" != "$ACCOUNT_ID" ]; then
  echo "AWS credentials belong to account $CALLER, expected $ACCOUNT_ID" >&2
  exit 1
fi

# 2. operator SSH key (created once if missing)
if [ ! -f "$SSH_KEY" ]; then
  ssh-keygen -t ed25519 -N "" -f "$SSH_KEY" -C rjb-operator
fi

# 3. only this machine's current public IP may SSH into the master
OPERATOR_IP=$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')
TF_VARS=(-var "allowed_ssh_cidr=$OPERATOR_IP/32" -var "ssh_public_key_path=$SSH_KEY.pub" -var "aws_account_id=$ACCOUNT_ID")
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30"

# 4. provision
cd "$HERE/terraform"
terraform init -input=false
terraform apply -auto-approve -input=false "${TF_VARS[@]}"
MASTER=$(terraform output -raw master_public_ip)
echo "master: $MASTER   workers: $(terraform output -json worker_private_ips)"

echo "waiting for the master bootstrap (packages, LaTeX, models, sources)..."
until $SSH ubuntu@"$MASTER" "test -f /var/lib/rjb-bootstrap-done" 2> /dev/null; do sleep 30; done

# 5. run the orchestrator detached on the master so a dropped connection does not stop it
$SSH ubuntu@"$MASTER" "tmux new-session -d -s rjb 'bash ~/nlp-project-/infra/scripts/orchestrate.sh 2>&1 | tee ~/orchestrate.log'"
echo "experiment running; follow it with:  $SSH ubuntu@$MASTER tail -f orchestrate.log"
until $SSH ubuntu@"$MASTER" "grep -q 'EXPERIMENT DONE' ~/orchestrate.log" 2> /dev/null; do sleep 120; done

# 6. results
mkdir -p "$OUT"
scp -i "$SSH_KEY" ubuntu@"$MASTER":rjb-results.tgz "$OUT/"
tar xzf "$OUT/rjb-results.tgz" -C "$OUT"
echo "results in $OUT"

# 7. teardown
if [ "$DESTROY" = "1" ]; then
  terraform destroy -auto-approve -input=false "${TF_VARS[@]}"
fi
