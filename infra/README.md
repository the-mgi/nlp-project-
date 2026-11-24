# Distributed RepoJudgeBench on AWS (Terraform)

One master and five workers (slaves) in a private VPC run the whole experiment:
benchmark construction in Docker, judging with llama.cpp, analysis and the paper.
Nothing here has been applied; it is the code to do so.

## Architecture

| Component | Where | What runs there |
|---|---|---|
| VPC `10.42.0.0/16` | one AZ | public subnet `10.42.1.0/24` (master, NAT gateway), private subnet `10.42.2.0/24` (workers) |
| Master (`m7i.xlarge`, 100 GB) | public subnet | orchestrator (`scripts/orchestrate.sh`), item builder, static baseline, analysis, LaTeX |
| 5 workers (`c7i.4xlarge`, 250 GB) | private subnet, no public IPs | Docker (task images), benchmark build shard, llama.cpp judges |
| NAT gateway | public subnet | outbound internet for the workers (Hugging Face, Docker mirror, PyPI, GitHub) |

Communication: you SSH to the master only (security group allows your IP). The master reaches
the workers over the private network with SSH + rsync using a cluster key Terraform generates;
workers accept SSH only from the master's security group.

Work split: phase 1 each worker builds shard `k` of 5 of the task list; phase 2 the master merges
the shards and builds the judge items; phase 3 each worker runs its judges
(w0: Qwen2.5-Coder-1.5B + context/point-wise, w1: Qwen2.5-Coder-3B, w2: Qwen3-1.7B + thinking +
context, w3: Qwen3-4B, w4: Llama-3.2-3B + Gemma-3-4B); phase 4 the master collects the verdicts and
produces `results/`, `paper/main.pdf` and `slides/slides.pdf`.

## Run

```bash
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars   # set allowed_ssh_cidr
SSH_KEY=~/.ssh/id_ed25519 DESTROY=1 bash infra/run_experiment.sh
```

The script runs `terraform apply`, waits for bootstrap, starts the orchestrator in `tmux` on the
master, waits for `EXPERIMENT DONE`, downloads `rjb-results.tgz` to `experiment-results/` and (with
`DESTROY=1`) runs `terraform destroy`. Follow progress with `ssh ubuntu@<master> tail -f orchestrate.log`.

Notes: EC2 and the NAT gateway are billed per hour; check AWS pricing first. The cluster SSH key is
passed through user data and stored in the Terraform state, so keep the state file private.
