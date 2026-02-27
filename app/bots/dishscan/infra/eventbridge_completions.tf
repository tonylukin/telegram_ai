resource "aws_cloudwatch_event_rule" "job_completed" {
  name           = "dishscan-job-completed-${var.env}"
  event_bus_name = aws_cloudwatch_event_bus.bus.name

  event_pattern = jsonencode({
    source      = ["dishscan.worker"]
    "detail-type" = ["dishscan.job.completed"]
  })
}

resource "aws_cloudwatch_event_target" "job_completed_to_sqs" {
  rule          = aws_cloudwatch_event_rule.job_completed.name
  event_bus_name = aws_cloudwatch_event_bus.bus.name
  arn           = aws_sqs_queue.completions.arn
}

# Allow EventBridge to send messages to the SQS queue
resource "aws_sqs_queue_policy" "completions_allow_eventbridge" {
  queue_url = aws_sqs_queue.completions.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowEventBridgeSendMessage"
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.completions.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.job_completed.arn
          }
        }
      }
    ]
  })
}