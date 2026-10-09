resource "aws_db_subnet_group" "main" {
  name = local.name
  subnet_ids = aws_subnet.db[*].id
}
resource "aws_db_instance" "main" {
  identifier = local.name
  engine = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class
  allocated_storage = 20
  max_allocated_storage = 100
  storage_encrypted = true
  db_name = "ecotwin"
  username = "ecotwin_admin"
  manage_master_user_password = true
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible = false
  backup_retention_period = 7
  multi_az = var.environment == "production"
  deletion_protection = var.environment == "production"
  auto_minor_version_upgrade = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${local.name}-final"
  enabled_cloudwatch_logs_exports = ["postgresql"]
}
resource "aws_secretsmanager_secret" "runtime" {
  for_each = toset(["api", "worker", "ingest", "migrate"])
  name = "${local.name}/${each.key}/database-url"
  description = "Operator populates a role-specific PostgreSQL connection URL after bootstrap; no plaintext in Terraform state."
}
