output "ecr_repo_url" {
  value = aws_ecr_repository.bot.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.dishscan.name
}

# output "ecs_service_name" {
#   value = aws_ecs_service.bot.name
# }

output "telegram_secret_arn" {
  value = aws_secretsmanager_secret.telegram_token.arn
}
