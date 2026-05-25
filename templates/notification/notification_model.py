from datetime import datetime, timezone
from bson import ObjectId
from mongo import notifications_collection


def _now():
    return datetime.now(timezone.utc)


def _to_object_id(value):
    if not value:
        return None

    value = str(value)

    if not ObjectId.is_valid(value):
        return None

    return ObjectId(value)


def serialize_notification(notification):
    if not notification:
        return None

    notification = dict(notification)

    notification["id"] = str(notification["_id"])
    del notification["_id"]

    if isinstance(notification.get("created_at"), datetime):
        notification["created_at"] = notification["created_at"].isoformat()

    if isinstance(notification.get("read_at"), datetime):
        notification["read_at"] = notification["read_at"].isoformat()

    return notification


def create_notification(
    recipient_user_id,
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None
):
    notification = {
        "recipient_user_id": str(recipient_user_id),
        "title": title,
        "message": message,
        "type": notification_type,
        "data": data or {},
        "is_read": False,
        "created_by": str(created_by) if created_by else None,
        "created_at": _now(),
        "read_at": None
    }

    result = notifications_collection.insert_one(notification)
    notification["_id"] = result.inserted_id

    return serialize_notification(notification)


def get_notifications_by_user(recipient_user_id, limit=50, only_unread=False):
    query = {
        "recipient_user_id": str(recipient_user_id)
    }

    if only_unread:
        query["is_read"] = False

    notifications = (
        notifications_collection
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
    )

    return [serialize_notification(item) for item in notifications]


def count_unread_notifications(recipient_user_id):
    return notifications_collection.count_documents({
        "recipient_user_id": str(recipient_user_id),
        "is_read": False
    })


def mark_notification_as_read(notification_id, recipient_user_id=None):
    object_id = _to_object_id(notification_id)

    if not object_id:
        return None

    query = {
        "_id": object_id
    }

    if recipient_user_id:
        query["recipient_user_id"] = str(recipient_user_id)

    notifications_collection.update_one(
        query,
        {
            "$set": {
                "is_read": True,
                "read_at": _now()
            }
        }
    )

    notification = notifications_collection.find_one(query)

    return serialize_notification(notification)


def mark_all_notifications_as_read(recipient_user_id):
    result = notifications_collection.update_many(
        {
            "recipient_user_id": str(recipient_user_id),
            "is_read": False
        },
        {
            "$set": {
                "is_read": True,
                "read_at": _now()
            }
        }
    )

    return result.modified_count


def delete_notification(notification_id, recipient_user_id=None):
    object_id = _to_object_id(notification_id)

    if not object_id:
        return False

    query = {
        "_id": object_id
    }

    if recipient_user_id:
        query["recipient_user_id"] = str(recipient_user_id)

    result = notifications_collection.delete_one(query)

    return result.deleted_count > 0