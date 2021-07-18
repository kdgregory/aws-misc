output "s3_bucket" {
  description = "The bucket used to hold deployment artifacts"
  value       = aws_s3_bucket_object.object.bucket
}


output "s3_key" {
  description = "The Amazon S3 key of the deployment package"
  value       = aws_s3_bucket_object.object.key
}


output "s3_version" {
  description = "The object's version identifier (if stored in a versioned bucket)"
  value       = aws_s3_bucket_object.object.version_id
}
