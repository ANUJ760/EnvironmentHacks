import signal
import time
from uuid import uuid4
import structlog
from ecotwin.config import get_settings
from ecotwin.db.session import session_factory
from ecotwin.jobs.db_queue import claim
from ecotwin.jobs.processor import process_job

def run_worker(once=False):
    settings=get_settings();worker_id=str(uuid4());stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    queue=None
    if settings.ecotwin_queue_backend=='sqs':
        from ecotwin.jobs.sqs_queue import SQSQueue
        queue=SQSQueue(settings.ecotwin_sqs_queue_url,settings.aws_region)
    while not stopping:
        messages=[]
        if queue:
            try:messages=queue.poll()
            except Exception:structlog.get_logger().warning('queue_poll_failed',reconciliation='database_poll')
        with session_factory()() as session:job=claim(session,worker_id,settings)
        if job:process_job(job,worker_id,settings,lambda:stopping)
        # Hints can be safely acknowledged even if another worker owns the job: DB leases remain authoritative.
        for message in messages:
            try:queue.acknowledge(message['ReceiptHandle'])
            except Exception:structlog.get_logger().warning('queue_ack_failed')
        if once:return
        if not job:time.sleep(settings.worker_poll_seconds)
