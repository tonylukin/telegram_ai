variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "env" {
  description = "Used to add to names"
  type        = string
}

variable "bedrock_model_id" {
  type    = string
  default = "global.anthropic.claude-sonnet-4-20250514-v1:0"
}

variable "bedrock_region" {
  type    = string
  default = "us-east-1"
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 45
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "assume_role_arn" {
  description = "ARN of the IAM role to assume for Terraform"
  type        = string
  default     = "arn:aws:iam::477975426794:role/TerraformAdminRole"
}

variable "sqs_queue_url" { # todo delete
  type        = string
  default     = "https://sqs.us-east-2.amazonaws.com/477975426794/dishscan-queue"
}

variable "completions_queue_url" { # todo delete
  type        = string
  default     = "https://sqs.us-east-2.amazonaws.com/477975426794/dishscan-completions-dishscan-dev"
}
