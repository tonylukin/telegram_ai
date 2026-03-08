resource "aws_dynamodb_table" "jobs" {
  name         = "${local.app}-jobs"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  tags = local.tags
}

############################################
# Image cache table
############################################
resource "aws_dynamodb_table" "dishscan_image_cache" {
  name         = "dishscan-image-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "image_hash"

  attribute {
    name = "image_hash"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Project = "dishscan"
    Service = "image-cache"
  }
}

############################################
# User history table
############################################
resource "aws_dynamodb_table" "dishscan_user_history" {
  name         = "dishscan-user-history"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "pk"
  range_key = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  tags = {
    Project = "dishscan"
    Service = "user-history"
  }
}
