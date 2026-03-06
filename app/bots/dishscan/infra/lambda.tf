data "archive_file" "worker_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda_worker"
  output_path = "${path.module}/.build/dishscan-worker.zip"
}

resource "aws_lambda_function" "worker" {
  function_name = "${local.app}-worker"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.handler"
  runtime       = "python3.12"

  filename         = data.archive_file.worker_zip.output_path
  source_code_hash = data.archive_file.worker_zip.output_base64sha256

  timeout     = var.lambda_timeout_seconds
  memory_size = 512

  environment {
    variables = {
      DISHSCAN_BEDROCK_REGION     = var.bedrock_region
      DISHSCAN_DDB_TABLE_NAME     = aws_dynamodb_table.jobs.name
      DISHSCAN_EVENT_BUS_NAME     = aws_cloudwatch_event_bus.bus.name
      DISHSCAN_BEDROCK_MODEL_ID   = var.bedrock_model_id
    }
  }

  tags = local.tags
}

resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.queue.arn
  function_name    = aws_lambda_function.worker.arn

  batch_size                         = 5
  maximum_batching_window_in_seconds = 5
}
