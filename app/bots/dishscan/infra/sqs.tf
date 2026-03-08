resource "aws_sqs_queue" "dlq" {
  name                     = "${local.app}-dlq"
  message_retention_seconds = 1209600
  tags                     = local.tags
}

resource "aws_sqs_queue" "queue" {
  name                        = "${local.app}-queue"
  visibility_timeout_seconds  = 120
  message_retention_seconds   = 345600
  receive_wait_time_seconds   = 10
  tags                        = local.tags

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}
