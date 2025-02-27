resource "aws_lambda_function" "mirror" {
  function_name = var.app_name
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = var.image_uri
  memory_size   = var.memory_size
  timeout       = var.timeout
  image_config {
    command           = ["app.lambda_handler"]
    entry_point       = []
    working_directory = "/var/task"
  }

  architectures = ["x86_64"]

  environment {
    variables = merge(
      {
        ENVIRONMENT = "aws"
      },
      var.environment_variables
    )
  }
  
  tags = var.tags
}

# CloudWatch Log Group with retention
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.app_name}"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.app_name}-schedule"
  description         = "Schedule for Jira to Airtable sync"
  schedule_expression = var.schedule_expression
  tags               = var.tags
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.schedule.name
  target_id = "LambdaFunction"
  arn       = aws_lambda_function.mirror.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mirror.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule.arn
}

# IAM Role
resource "aws_iam_role" "lambda_role" {
  name = "${var.app_name}-lambda-role"
  force_detach_policies = true

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

# CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Secrets Manager access
resource "aws_iam_role_policy" "secrets_access" {
  name = "${var.app_name}-secrets-access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = values(var.secrets)
      }
    ]
  })
}

# SNS Topic for alarms
resource "aws_sns_topic" "lambda_alarms" {
  name = "${var.app_name}-alarms"
  tags = var.tags
}

# Memory utilization alarms
resource "aws_cloudwatch_metric_alarm" "memory_80" {
  alarm_name          = "${var.app_name}-memory-utilization-80"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name        = "memory_utilization"
  namespace          = "AWS/Lambda"
  period             = "300"  # 5 minutes
  statistic          = "Maximum"
  threshold          = "80"
  alarm_description  = "Lambda function memory utilization is above 80%"
  alarm_actions      = [aws_sns_topic.lambda_alarms.arn]
  ok_actions         = [aws_sns_topic.lambda_alarms.arn]

  dimensions = {
    FunctionName = aws_lambda_function.mirror.function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "memory_90" {
  alarm_name          = "${var.app_name}-memory-utilization-90"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name        = "memory_utilization"
  namespace          = "AWS/Lambda"
  period             = "300"  # 5 minutes
  statistic          = "Maximum"
  threshold          = "90"
  alarm_description  = "Lambda function memory utilization is above 90%"
  alarm_actions      = [aws_sns_topic.lambda_alarms.arn]
  ok_actions         = [aws_sns_topic.lambda_alarms.arn]

  dimensions = {
    FunctionName = aws_lambda_function.mirror.function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "memory_95" {
  alarm_name          = "${var.app_name}-memory-utilization-95"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name        = "memory_utilization"
  namespace          = "AWS/Lambda"
  period             = "300"  # 5 minutes
  statistic          = "Maximum"
  threshold          = "95"
  alarm_description  = "Lambda function memory utilization is above 95%"
  alarm_actions      = [aws_sns_topic.lambda_alarms.arn]
  ok_actions         = [aws_sns_topic.lambda_alarms.arn]

  dimensions = {
    FunctionName = aws_lambda_function.mirror.function_name
  }

  tags = var.tags
}

# Error rate alarm (good to have alongside memory alarms)
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.app_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name        = "Errors"
  namespace          = "AWS/Lambda"
  period             = "300"  # 5 minutes
  statistic          = "Sum"
  threshold          = "0"
  alarm_description  = "Lambda function has errors"
  alarm_actions      = [aws_sns_topic.lambda_alarms.arn]
  ok_actions         = [aws_sns_topic.lambda_alarms.arn]

  dimensions = {
    FunctionName = aws_lambda_function.mirror.function_name
  }

  tags = var.tags
}

# Outputs
output "function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.mirror.function_name
}

output "function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.mirror.arn
}

output "role_arn" {
  description = "ARN of the Lambda IAM role"
  value       = aws_iam_role.lambda_role.arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for Lambda alarms"
  value       = aws_sns_topic.lambda_alarms.arn
}
