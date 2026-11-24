variable "aws_account_id" {
  description = "AWS account the cluster is created in; Terraform refuses to run against any other account"
  type        = string
  default     = "602170263568"
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "owner_tag" {
  description = "Value of the Owner tag on every resource"
  type        = string
  default     = "nlp-project"
}

variable "vpc_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Subnet of the master (has a public IP for SSH)"
  type        = string
  default     = "10.42.1.0/24"
}

variable "private_subnet_cidr" {
  description = "Subnet of the workers (no public IPs; internet egress via NAT)"
  type        = string
  default     = "10.42.2.0/24"
}

variable "worker_count" {
  description = "Number of worker (slave) nodes"
  type        = number
  default     = 5
}

variable "master_instance_type" {
  type    = string
  default = "m7i.xlarge" # 4 vCPU, 16 GiB: orchestration, analysis, LaTeX
}

variable "worker_instance_type" {
  type    = string
  default = "c7i.4xlarge" # 16 vCPU (Sapphire Rapids, AMX), 32 GiB: Docker builds + llama.cpp judges
}

variable "master_disk_gb" {
  type    = number
  default = 100
}

variable "worker_disk_gb" {
  description = "Docker images of the tasks are 1-8 GB each"
  type        = number
  default     = 250
}

variable "ssh_public_key_path" {
  description = "Operator SSH public key, used to log in to the master"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH into the master; run_experiment.sh passes the operator's detected public IP as /32"
  type        = string
  validation {
    condition     = can(cidrhost(var.allowed_ssh_cidr, 0))
    error_message = "allowed_ssh_cidr must be a valid IPv4 CIDR block, e.g. a single address with /32."
  }
}

variable "repo_url" {
  type    = string
  default = "https://github.com/the-mgi/nlp-project-.git"
}

variable "repo_branch" {
  type    = string
  default = "ccr-92223913-pplduy"
}
