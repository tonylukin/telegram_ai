########################
# Bot role (ECS task) #
########################

data "aws_iam_policy_document" "bot_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "bot_role" {
  name               = "${local.app}-bot-role"
  assume_role_policy = data.aws_iam_policy_document.bot_assume_role.json
  tags               = local.tags
  # lifecycle {
  #   prevent_destroy = true
  # }
}

data "aws_iam_policy_document" "bot_policy" {

  statement {
    sid     = "S3PutUploads"
    effect  = "Allow"
    actions = ["s3:PutObject", "s3:PutObjectTagging"]
    resources = [
      "${aws_s3_bucket.uploads.arn}/uploads/*"
    ]
  }

  statement {
    sid     = "SQSSend"
    effect  = "Allow"
    actions = ["sqs:SendMessage"]
    resources = [
      aws_sqs_queue.queue.arn
    ]
  }

  statement {
    sid     = "DynamoWrite"
    effect  = "Allow"
    actions = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
    resources = [
      aws_dynamodb_table.jobs.arn
    ]
  }

  statement {
    sid     = "EventBridgePut"
    effect  = "Allow"
    actions = ["events:PutEvents"]
    resources = [
      aws_cloudwatch_event_bus.bus.arn
    ]
  }
}

resource "aws_iam_role_policy" "bot_inline" {
  role   = aws_iam_role.bot_role.id
  policy = data.aws_iam_policy_document.bot_policy.json
}

########################
# Lambda worker role  #
########################

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${local.app}-worker-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = local.tags
  # lifecycle {
  #   prevent_destroy = true
  # }
}

data "aws_iam_policy_document" "lambda_policy" {

  statement {
    sid     = "S3GetUploads"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    resources = [
      "${aws_s3_bucket.uploads.arn}/uploads/*"
    ]
  }

  statement {
    sid     = "DynamoUpdate"
    effect  = "Allow"
    actions = ["dynamodb:UpdateItem", "dynamodb:GetItem"]
    resources = [
      aws_dynamodb_table.jobs.arn
    ]
  }

  statement {
    sid     = "BedrockInvoke"
    effect  = "Allow"
    actions = [
      "bedrock-runtime:InvokeModel",
      "bedrock-runtime:InvokeModelWithResponseStream"
    ]
    resources = ["*"]
  }

  statement {
    sid     = "CloudWatchLogs"
    effect  = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["*"]
  }

  statement {
    sid    = "SQSPoll"
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility"
    ]
    resources = [
      aws_sqs_queue.queue.arn
    ]
  }
}

resource "aws_iam_role_policy" "lambda_inline" {
  role   = aws_iam_role.lambda_role.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy" "lambda_bedrock_invoke" {
  name = "dishscan-worker-bedrock-invoke"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvokeClaude"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:us-east-1::foundation-model/anthropic.*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_put_events" {
  name = "dishscan-worker-put-events"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect  = "Allow"
        Action  = ["events:PutEvents"]
        Resource = aws_cloudwatch_event_bus.bus.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "bot_read_completions_queue" {
  name = "dishscan-bot-read-completions-queue"
  role = aws_iam_role.bot_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = aws_sqs_queue.completions.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.jobs.arn
      }
    ]
  })
}

# todo no need this role policy cuz should be subscribed manually by account owner to the Bedrock marketplace model, but adding it here for completeness and ease of deployment
resource "aws_iam_role_policy" "lambda_bedrock_marketplace" {
  name = "dishscan-worker-bedrock-marketplace"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "MarketplaceForBedrockAutoEnable"
        Effect = "Allow"
        Action = [
          "aws-marketplace:ViewSubscriptions",
          "aws-marketplace:Subscribe",
          "aws-marketplace:Unsubscribe"
        ]
        Resource = "*"
      }
    ]
  })
}
