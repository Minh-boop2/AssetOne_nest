from datetime import datetime, timezone, timedelta
from bson import ObjectId


VALID_ACTIVITY_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

VN_TZ = timezone(timedelta(hours=7))


def now_vietnam():
    return datetime.now(VN_TZ)


def format_datetime_vietnam(value):
    if not value:
        return None

    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    vietnam_time = value.astimezone(VN_TZ)

    return vietnam_time.strftime("%d/%m/%Y %H:%M")


def is_valid_object_id(id):
    return ObjectId.is_valid(id)


def activity_serializer(activity):
    return {
        "id": str(activity["_id"]),
        "user_id": str(activity.get("user_id")) if activity.get("user_id") else None,
        "employee_code": activity.get("employee_code"),
        "full_name": activity.get("full_name"),
        "email": activity.get("email"),
        "role": activity.get("role"),

        "action": activity.get("action"),
        "module": activity.get("module"),
        "method": activity.get("method"),
        "path": activity.get("path"),
        "status_code": activity.get("status_code"),

        "target_id": activity.get("target_id"),
        "target_name": activity.get("target_name"),

        "metadata": activity.get("metadata", {}),

        "created_at": format_datetime_vietnam(activity.get("created_at")),
    }


def create_activity_model(data):
    return {
        "user_id": data.get("user_id"),
        "employee_code": data.get("employee_code"),
        "full_name": data.get("full_name"),
        "email": data.get("email"),
        "role": data.get("role"),

        "action": data.get("action"),
        "module": data.get("module"),
        "method": data.get("method"),
        "path": data.get("path"),
        "status_code": data.get("status_code"),

        "target_id": data.get("target_id"),
        "target_name": data.get("target_name"),

        "metadata": data.get("metadata", {}),

        "created_at": now_vietnam(),
    }