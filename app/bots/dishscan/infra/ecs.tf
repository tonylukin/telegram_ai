data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

# Use default VPC/subnets to avoid extra infra for now
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_ecs_cluster" "dishscan" {
  name = "${local.app}-cluster"
  tags = local.tags
}

resource "aws_cloudwatch_log_group" "bot" {
  name              = "/ecs/${local.app}-bot"
  retention_in_days = 14
  tags              = local.tags
}

# ECR repo for the bot image
resource "aws_ecr_repository" "bot" {
  name                 = "${local.app}-bot"
  image_tag_mutability = "MUTABLE"
  tags                 = local.tags
}

# Secret (value will be set via CLI to avoid putting token into tfstate)
resource "aws_secretsmanager_secret" "telegram_token" {
  name        = "${local.app}/telegram_bot_token/${var.env}"
  description = "Telegram bot token for dishscan polling bot"
  tags        = local.tags

  lifecycle {
    prevent_destroy = true
  }
}

# Security group: no inbound, allow all outbound
resource "aws_security_group" "bot" {
  name        = "${local.app}-bot-sg"
  description = "ECS Fargate SG for dishscan bot (egress only)"
  vpc_id      = data.aws_vpc.default.id
  tags        = local.tags

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ECS task execution role (pull image, write logs, read secret)
data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${local.app}-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_exec_managed" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn  = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow execution role to read the telegram token secret
data "aws_iam_policy_document" "ecs_exec_secret_read" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [aws_secretsmanager_secret.telegram_token.arn]
  }
}

resource "aws_iam_role_policy" "ecs_exec_secret_read" {
  name   = "${local.app}-ecs-exec-secret-read"
  role   = aws_iam_role.ecs_task_execution_role.id
  policy = data.aws_iam_policy_document.ecs_exec_secret_read.json
}

# Task definition: IMPORTANT — task_role_arn is your bot role from Terraform (S3/SQS/DDB/EventBridge)
resource "aws_ecs_task_definition" "bot" {
  family                   = "${local.app}-bot"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory

  execution_role_arn = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn      = aws_iam_role.bot_role.arn

  container_definitions = jsonencode([
    {
      name      = "dishscan-bot"
      image     = "${aws_ecr_repository.bot.repository_url}:${var.bot_image_tag}"
      essential = true
      command = ["python3", "app/bots/dishscan/main.py"]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.bot.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = "ecs"
        }
      }

      environment = [
        { name = "DISHSCAN_AWS_REGION",      value = var.aws_region },
        { name = "DISHSCAN_S3_BUCKET",       value = aws_s3_bucket.uploads.bucket },
        { name = "DISHSCAN_SQS_QUEUE_URL",   value = var.sqs_queue_url },
        { name = "DISHSCAN_DDB_TABLE_NAME",  value = aws_dynamodb_table.jobs.name },
        { name = "DISHSCAN_EVENT_BUS_NAME",  value = aws_cloudwatch_event_bus.bus.name },
        { name = "DISHSCAN_COMPLETIONS_QUEUE_URL", value = var.completions_queue_url }
      ]
    }
  ])

  tags = local.tags
  depends_on = [
    aws_cloudwatch_log_group.bot
  ]
}

resource "aws_ecs_service" "bot" {
  name            = "${local.app}-bot"
  cluster         = aws_ecs_cluster.dishscan.id
  task_definition = aws_ecs_task_definition.bot.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = data.aws_subnets.default.ids
    security_groups = [aws_security_group.bot.id]
    assign_public_ip = true
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  tags = local.tags
}
