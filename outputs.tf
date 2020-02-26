output "function_name" {
  description = "The name of the Lambda function."
  value       = aws_lambda_function.pipeline_set_version.id
}
