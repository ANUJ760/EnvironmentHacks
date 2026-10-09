"""Messages are hints only; DB polling reconciles failed publication."""

import json
from uuid import UUID

import boto3
from botocore.config import Config


class SQSQueue:
    def __init__(self, url, region, client=None):
        self.url = url
        self.client = client or boto3.client(
            "sqs",
            region_name=region,
            config=Config(
                connect_timeout=5, read_timeout=30, retries={"max_attempts": 3, "mode": "standard"}
            ),
        )

    def publish(self, job_id):
        UUID(str(job_id))
        self.client.send_message(QueueUrl=self.url, MessageBody=json.dumps({"job_id": str(job_id)}))

    def poll(self):
        return self.client.receive_message(
            QueueUrl=self.url, MaxNumberOfMessages=10, WaitTimeSeconds=1, VisibilityTimeout=240
        ).get("Messages", [])

    def acknowledge(self, receipt):
        self.client.delete_message(QueueUrl=self.url, ReceiptHandle=receipt)
