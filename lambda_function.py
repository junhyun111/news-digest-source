from __future__ import annotations

import logging

from job import run_job


logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """Run the news digest when invoked by AWS Lambda."""
    exit_code = run_job()
    if exit_code:
        raise RuntimeError(f"News digest job failed with exit code {exit_code}.")

    logger.info("News digest sent successfully")
    return {
        "statusCode": 200,
        "body": "News digest sent successfully",
    }
