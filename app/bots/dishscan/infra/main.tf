terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }

    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
  profile = "dishscan"

  assume_role {
    role_arn     = "arn:aws:iam::477975426794:role/TerraformAdminRole"
    session_name = "terraform"
  }
}

locals {
  app = "dishscan"

  tags = merge(var.tags, {
    app = local.app
  })
}
