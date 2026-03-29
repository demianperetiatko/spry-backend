import json
import logging
import uuid

from google.cloud import pubsub_v1

from src.core.config import settings

logger = logging.getLogger(__name__)


def publish_resync_organization(organization_id: uuid.UUID) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.GCP_PROJECT_ID, settings.PUBSUB_RESYNC_TOPIC)
    data = json.dumps({"organization_id": str(organization_id)}).encode("utf-8")
    future = publisher.publish(topic_path, data)
    message_id = future.result()
    logger.info(f"Published resync message for org={organization_id}, message_id={message_id}")