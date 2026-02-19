variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "name_suffix" {
  description = "Used to make S3 bucket name unique"
  type        = string
}

variable "bedrock_model_id" {
  type    = string
  default = "anthropic.claude-3-sonnet-20240229-v1:0"
}

variable "TELEGRAM_DISHSCAN_BOT_TOKEN" {
  type      = string
  # sensitive = true
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 45
}

variable "tags" {
  type    = map(string)
  default = {}
}
