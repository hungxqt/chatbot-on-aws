terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  backend "s3" {}
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  name_prefix = var.project_name
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)
  az_keys     = ["az1", "az2", "az3"]

  subnet_tiers = {
    public = {
      az1 = "10.0.1.0/24"
      az2 = "10.0.2.0/24"
      az3 = "10.0.3.0/24"
    }
    private = {
      az1 = "10.0.4.0/24"
      az2 = "10.0.5.0/24"
      az3 = "10.0.6.0/24"
    }
    database = {
      az1 = "10.0.7.0/24"
      az2 = "10.0.8.0/24"
      az3 = "10.0.9.0/24"
    }
    firewall = {
      az1 = "10.0.10.0/24"
      az2 = "10.0.11.0/24"
      az3 = "10.0.12.0/24"
    }
  }

  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
  region     = data.aws_region.current.region

  generated_secret_exclude_characters = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
}
