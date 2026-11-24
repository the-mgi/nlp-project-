aws_account_id       = "602170263568"
region               = "us-east-1"
worker_count         = 5
master_instance_type = "m7i.xlarge"
worker_instance_type = "c7i.4xlarge"
ssh_public_key_path  = "~/.ssh/id_ed25519.pub"
repo_url             = "https://github.com/the-mgi/nlp-project-.git"
repo_branch          = "ccr-92223913-pplduy"
# allowed_ssh_cidr is detected and passed by ../run_experiment.sh
