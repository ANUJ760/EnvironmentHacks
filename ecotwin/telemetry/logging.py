import logging
import structlog

SENSITIVE={'authorization','password','token','api_key','database_url','secret','x-api-key'}

def redact(logger,method,event):
    def clean(value):
        if isinstance(value,dict):return {key:'[REDACTED]' if any(secret in key.lower() for secret in SENSITIVE) else clean(item) for key,item in value.items()}
        if isinstance(value,list):return [clean(item) for item in value]
        return value
    return clean(event)

def configure(level='INFO'):
    logging.basicConfig(level=level)
    structlog.configure(processors=[structlog.contextvars.merge_contextvars,structlog.processors.TimeStamper(fmt='iso'),structlog.processors.add_log_level,redact,structlog.processors.JSONRenderer()])
