resource "aws_cloudwatch_event_bus" "bus" {
  name = "${local.app}-bus"
  tags = local.tags
}
