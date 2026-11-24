data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# operator -> master login key
resource "aws_key_pair" "operator" {
  key_name   = "rjb-operator"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

# master -> workers key for the private network (generated, never leaves the VPC)
resource "tls_private_key" "cluster" {
  algorithm = "ED25519"
}

resource "aws_instance" "worker" {
  count                  = var.worker_count
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.worker_instance_type
  subnet_id              = aws_subnet.private.id
  vpc_security_group_ids = [aws_security_group.worker.id]
  key_name               = aws_key_pair.operator.key_name

  root_block_device {
    volume_size = var.worker_disk_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/templates/bootstrap.sh.tftpl", {
    role               = "worker"
    index              = count.index
    repo_url           = var.repo_url
    repo_branch        = var.repo_branch
    cluster_public_key = tls_private_key.cluster.public_key_openssh
    cluster_private_key = ""
    worker_ips         = ""
  })

  tags       = { Name = "rjb-worker-${count.index}", Role = "worker" }
  depends_on = [aws_nat_gateway.nat, aws_route_table_association.private]
}

resource "aws_instance" "master" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.master_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.master.id]
  key_name               = aws_key_pair.operator.key_name

  root_block_device {
    volume_size = var.master_disk_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/templates/bootstrap.sh.tftpl", {
    role                = "master"
    index               = 0
    repo_url            = var.repo_url
    repo_branch         = var.repo_branch
    cluster_public_key  = tls_private_key.cluster.public_key_openssh
    cluster_private_key = tls_private_key.cluster.private_key_openssh
    worker_ips          = join(" ", aws_instance.worker[*].private_ip)
  })

  tags = { Name = "rjb-master", Role = "master" }
}
