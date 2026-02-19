variable "ecs_cpu" {
  type    = string
  default = "256"
}

variable "ecs_memory" {
  type    = string
  default = "512"
}

variable "ecs_desired_count" {
  type    = number
  default = 1
}

variable "bot_image_tag" {
  type    = string
  default = "latest"
}
