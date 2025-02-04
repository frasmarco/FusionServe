import logging
import logging.config

import uvicorn.config
from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    envvar_prefix=False,
    settings_files=["settings.yaml", ".secrets.yaml"],
    environments=True,
    validators=[
        # Validator("rabbit_host", default="rabbitmq"),
        # Validator("pg_host", default="tsportal-pg"),
        Validator("log_level", default="INFO"),
    ],
)

logger = logging.getLogger(settings.app_name)
logging.config.dictConfig(
    {
        "version": 1,
        "handlers": {
            "stream_handler": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "detailed",
            }
        },
        "formatters": {
            "detailed": {"format": "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"}
        },
        "loggers": {
            settings.app_name: {
                "handlers": ["stream_handler"],
                "level": settings.log_level,
            }
        },
    }
    | uvicorn.config.LOGGING_CONFIG
)
