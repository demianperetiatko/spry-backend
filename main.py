import functions_framework
import base64


@functions_framework.cloud_event
def update_data(cloud_event):
    data = cloud_event.data or {}
    msg = None
    try:
        msg_b64 = data["message"]["data"]
        msg = base64.b64decode(msg_b64).decode("utf-8")
    except Exception:
        # For other event types, just log the whole payload
        msg = str(data)

    print(f"Event ID: {cloud_event['id']}")
    print(f"Event Type: {cloud_event['type']}")
    print(f"Message: {msg}")
