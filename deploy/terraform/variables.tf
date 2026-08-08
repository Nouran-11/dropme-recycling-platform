variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  # t3.medium is not free-tier eligible; RunInstances rejects it on a free-tier
  # account. m7i-flex.large launches on such accounts.
  default     = "m7i-flex.large"
}

variable "my_ip" {
  description = "CIDR allowed to reach SSH (port 22), e.g. 203.0.113.4/32"
  type        = string
}

variable "key_name" {
  description = "Name of an existing EC2 key pair for SSH access"
  type        = string
}

variable "repo_url" {
  description = "Public git repository to build on the instance"
  type        = string
  default     = "https://github.com/Nouran-11/dropme-recycling-platform.git"
}
