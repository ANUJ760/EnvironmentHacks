"""Explicit AWS release harness. Dry-run by default; never runs Terraform apply."""

import argparse
import base64
import json
import re
import subprocess
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]


def output_values(path):
    return {key: value["value"] for key, value in json.loads(path.read_text()).items()}


def task_request(outputs, kind, bundle=None):
    bootstrap = kind == "bootstrap"
    request = {
        "cluster": outputs["ecs_cluster_name"],
        "taskDefinition": outputs[
            "ingest_task_definition_arn" if bootstrap else "migration_task_definition_arn"
        ],
        "launchType": "FARGATE",
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": outputs["private_subnet_ids"],
                "securityGroups": [
                    outputs[
                        "ingestion_security_group_id"
                        if bootstrap
                        else "migration_security_group_id"
                    ]
                ],
                "assignPublicIp": "DISABLED",
            }
        },
    }
    if bootstrap:
        command = [
            "python",
            "scripts/bootstrap_data.py",
            "--data-dir",
            "/app/cache/data",
            "--maps-dir",
            "/app/cache/maps",
        ]
        if bundle:
            if not re.fullmatch(r"manifests/bundles/[a-f0-9]{64}\.json", bundle):
                raise ValueError("An immutable private bundle index is required")
            command += ["--bundle-index", bundle]
        request["overrides"] = {"containerOverrides": [{"name": "ingest", "command": command}]}
    if (
        not request["taskDefinition"]
        or not request["networkConfiguration"]["awsvpcConfiguration"]["subnets"]
    ):
        raise ValueError("Apply the task-registration stage before running migration or ingestion")
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["images", "migrate", "bootstrap", "status"])
    parser.add_argument(
        "--outputs", type=Path, required=True, help="terraform output -json file, never commit it"
    )
    parser.add_argument("--bundle-index")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Explicitly build/push images or launch a one-off paid AWS task",
    )
    args = parser.parse_args()
    outputs = output_values(args.outputs)
    region = outputs["aws_region"]
    if args.action == "images":
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        plan = {
            "backend": f"{outputs['ecr_repository_url']}:{revision}",
            "frontend": f"{outputs['frontend_ecr_repository_url']}:{revision}",
            "data_required": "Run local.py download first; tree asset must exist before frontend build",
        }
        print(json.dumps(plan, indent=2))
        if not args.apply:
            return
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
            raise ValueError("Release images require a committed, clean worktree")
        if not (ROOT / "frontend/public/maps/zurich-trees.geojson").is_file():
            raise ValueError("Download and generate map assets first")
        ecr = boto3.client("ecr", region_name=region)
        for name, context in [("backend", "."), ("frontend", "frontend")]:
            uri = plan[name]
            if not re.fullmatch(
                r"\d+\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/[a-z0-9/_-]+:[a-f0-9]{40}", uri
            ):
                raise ValueError("Invalid ECR image destination")
            registry, repository = uri.split("/", 1)
            repository = repository.rsplit(":", 1)[0]
            token = ecr.get_authorization_token()["authorizationData"][0]["authorizationToken"]
            user, password = base64.b64decode(token).decode().split(":", 1)
            subprocess.run(
                ["docker", "login", "--username", user, "--password-stdin", registry],
                input=password,
                text=True,
                check=True,
            )
            subprocess.run(
                [
                    "docker",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--build-arg",
                    f"GIT_REVISION={revision}",
                    "-t",
                    uri,
                    context,
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run(["docker", "push", uri], check=True)
            digest = ecr.describe_images(
                repositoryName=repository, imageIds=[{"imageTag": revision}]
            )["imageDetails"][0]["imageDigest"]
            print(
                json.dumps(
                    {
                        "terraform_variable": "image_uri"
                        if name == "backend"
                        else "frontend_image_uri",
                        "value": f"{registry}/{repository}@{digest}",
                    }
                )
            )
        return
    if args.action == "status":
        print(
            json.dumps(
                {
                    "cluster": outputs["ecs_cluster_name"],
                    "frontend": outputs.get("frontend_https_url"),
                    "api": outputs.get("api_https_url"),
                }
            )
        )
        return
    request = task_request(outputs, args.action, args.bundle_index)
    print(
        json.dumps(
            {"action": args.action, "paid_task_launch": args.apply, "request": request}, indent=2
        )
    )
    if not args.apply:
        return
    client = boto3.client("ecs", region_name=region)
    response = client.run_task(**request)
    if response.get("failures") or not response.get("tasks"):
        raise RuntimeError("ECS task launch failed: " + json.dumps(response.get("failures", [])))
    task = response["tasks"][0]["taskArn"]
    client.get_waiter("tasks_stopped").wait(
        cluster=request["cluster"], tasks=[task], WaiterConfig={"Delay": 15, "MaxAttempts": 240}
    )
    stopped = client.describe_tasks(cluster=request["cluster"], tasks=[task])["tasks"][0]
    if any(
        container.get("exitCode") != 0 for container in stopped.get("containers", [])
    ) or not stopped.get("containers"):
        raise RuntimeError(
            "Task failed. Inspect CloudWatch logs and stopped reason: "
            + stopped.get("stoppedReason", "unknown")
        )
    print(json.dumps({"task": task, "exit_code": 0}))


if __name__ == "__main__":
    main()
