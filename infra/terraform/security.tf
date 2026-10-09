resource "aws_security_group" "alb" {
  name = "${local.name}-alb"
  vpc_id = aws_vpc.main.id
  ingress { from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"] }
  egress { from_port = 8000
    to_port = 8000
    protocol = "tcp"
    cidr_blocks = aws_subnet.app[*].cidr_block }
}
resource "aws_security_group" "tasks" {
  for_each = toset(["api", "worker", "ingest", "migrate"])
  name = "${local.name}-${each.key}"
  vpc_id = aws_vpc.main.id
  dynamic "ingress" {
    for_each = each.key == "api" ? [1] : []
    content { from_port = 8000
      to_port = 8000
      protocol = "tcp"
      security_groups = [aws_security_group.alb.id] }
  }
  egress { from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"] }
  egress { from_port = 5432
    to_port = 5432
    protocol = "tcp"
    cidr_blocks = aws_subnet.db[*].cidr_block }
  egress { from_port = 53
    to_port = 53
    protocol = "udp"
    cidr_blocks = [aws_vpc.main.cidr_block] }
}
resource "aws_security_group" "db" {
  name = "${local.name}-database"
  vpc_id = aws_vpc.main.id
  ingress { from_port = 5432
    to_port = 5432
    protocol = "tcp"
    security_groups = [for sg in aws_security_group.tasks : sg.id] }
}
resource "aws_iam_role" "execution" {
  name = "${local.name}-execution"
  assume_role_policy = jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Principal={Service="ecs-tasks.amazonaws.com"},Action="sts:AssumeRole"}]})
}
resource "aws_iam_role_policy_attachment" "execution" {
  role = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role_policy" "secrets" {
  count = var.enable_services ? 1 : 0
  role = aws_iam_role.execution.id
  policy = jsonencode({Version="2012-10-17",Statement=[{Effect="Allow",Action=["secretsmanager:GetSecretValue"],Resource=concat(values(var.database_secret_arns),var.openaq_secret_arn != "" ? [var.openaq_secret_arn] : [])}]})
}
resource "aws_iam_role" "task" {
  for_each = toset(["api", "worker", "ingest", "migrate"])
  name = "${local.name}-${each.key}-task"
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}
resource "aws_iam_role_policy" "task" {
  for_each = toset(["api", "worker", "ingest"])
  role = aws_iam_role.task[each.key].id
  policy = jsonencode({Version="2012-10-17",Statement=concat(
    [{Effect="Allow",Action=["s3:GetObject"],Resource=["${aws_s3_bucket.data.arn}/ecotwin/raw/*","${aws_s3_bucket.data.arn}/ecotwin/processed/*","${aws_s3_bucket.data.arn}/ecotwin/manifests/*"]}],
    each.key == "ingest" ? [{Effect="Allow",Action=["s3:PutObject"],Resource=["${aws_s3_bucket.data.arn}/ecotwin/raw/*","${aws_s3_bucket.data.arn}/ecotwin/processed/*","${aws_s3_bucket.data.arn}/ecotwin/manifests/*"]}] : [],
    each.key == "worker" ? [{Effect="Allow",Action=["s3:PutObject","s3:GetObject"],Resource=["${aws_s3_bucket.data.arn}/ecotwin/results/*"]},{Effect="Allow",Action=["sqs:ReceiveMessage","sqs:DeleteMessage","sqs:ChangeMessageVisibility","sqs:GetQueueAttributes"],Resource=[aws_sqs_queue.jobs.arn]}] : [],
    each.key == "api" ? [{Effect="Allow",Action=["sqs:SendMessage"],Resource=[aws_sqs_queue.jobs.arn]}] : []
  )})
}
