resource "aws_sqs_queue" "completions" {
  name                       = "dishscan-completions-${var.env}"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
}

output "completions_queue_url" {
  value = aws_sqs_queue.completions.url
}

output "completions_queue_arn" {
  value = aws_sqs_queue.completions.arn
}
