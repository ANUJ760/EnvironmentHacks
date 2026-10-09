import structlog

from ecotwin.config import get_settings


def publish_hint(job_id):
    settings = get_settings()
    if settings.ecotwin_queue_backend == "sqs":
        from ecotwin.jobs.sqs_queue import SQSQueue

        try:
            SQSQueue(settings.ecotwin_sqs_queue_url, settings.aws_region).publish(job_id)
        except Exception:
            structlog.get_logger().warning(
                "queue_publish_failed", job_id=str(job_id), reconciliation="database_poll"
            )
