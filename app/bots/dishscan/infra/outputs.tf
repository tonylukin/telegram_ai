output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}

output "queue_url" {
  value = aws_sqs_queue.queue.url
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}

output "ddb_table" {
  value = aws_dynamodb_table.jobs.name
}

output "event_bus_name" {
  value = aws_cloudwatch_event_bus.bus.name
}

output "bot_role_arn" {
  value = aws_iam_role.bot_role.arn
}

output "lambda_role_arn" {
  value = aws_iam_role.lambda_role.arn
}
