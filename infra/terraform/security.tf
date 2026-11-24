# master: SSH from your IP only; everything from the workers
resource "aws_security_group" "master" {
  name        = "rjb-master"
  description = "RepoJudgeBench master"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from the operator"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "rjb-master-sg" }
}

# workers: SSH only from the master, all traffic among workers inside the VPC
resource "aws_security_group" "worker" {
  name        = "rjb-worker"
  description = "RepoJudgeBench workers"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "SSH / rsync from the master"
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = [aws_security_group.master.id]
  }

  ingress {
    description = "worker to worker"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "rjb-worker-sg" }
}

resource "aws_security_group_rule" "master_from_workers" {
  type                     = "ingress"
  description              = "all traffic from the workers"
  from_port                = 0
  to_port                  = 0
  protocol                 = "-1"
  security_group_id        = aws_security_group.master.id
  source_security_group_id = aws_security_group.worker.id
}
