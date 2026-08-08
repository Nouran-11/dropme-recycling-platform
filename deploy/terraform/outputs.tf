output "public_ip" {
  description = "Elastic IP of the instance"
  value       = aws_eip.this.public_ip
}

output "url" {
  description = "HTTPS URL served by Caddy via sslip.io"
  value       = "https://${aws_eip.this.public_ip}.sslip.io"
}

output "ssh" {
  description = "SSH command"
  value       = "ssh ubuntu@${aws_eip.this.public_ip}"
}
