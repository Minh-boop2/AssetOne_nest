from datetime import datetime, timezone, timedelta
from bson import ObjectId
from werkzeug.security import generate_password_hash


VALID_ROLES = ["ADMIN", "QUAN_LY", "NHAN_VIEN"]
VALID_STATUS = ["HOAT_DONG", "NGUNG_HOAT_DONG"]

VN_TZ = timezone(timedelta(hours=7))


def now_vietnam():
    return datetime.now(VN_TZ)


def format_datetime_vietnam(value):
    if not value:
        return None

    if isinstance(value, str):
        return value

    # MongoDB thường trả datetime dạng UTC nhưng không có timezone
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    vietnam_time = value.astimezone(VN_TZ)

    return vietnam_time.strftime("%d/%m/%Y %H:%M")


def user_serializer(user):
    return {
        "id": str(user["_id"]),
        "employee_code": user.get("employee_code"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "department": user.get("department"),
        "floor": user.get("floor"),
        "role": user.get("role"),
        "status": user.get("status"),

        # Dùng created_at làm ngày tham gia
        "created_at": format_datetime_vietnam(user.get("created_at")),
        "updated_at": format_datetime_vietnam(user.get("updated_at")),
    }


def create_user_model(data):
    now = now_vietnam()

    return {
        "employee_code": data.get("employee_code"),
        "full_name": data.get("full_name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "department": data.get("department"),
        "floor": data.get("floor"),
        "role": data.get("role", "NHAN_VIEN"),
        "status": data.get("status", "HOAT_DONG"),
        "password_hash": generate_password_hash(data.get("password")),
        "created_at": now,
        "updated_at": now,
    }


def update_user_model(data):
    allowed_fields = [
        "employee_code",
        "full_name",
        "email",
        "phone",
        "department",
        "floor",
        "role",
        "status",
    ]

    update_data = {}

    for field in allowed_fields:
        if field in data:
            update_data[field] = data[field]

    update_data["updated_at"] = now_vietnam()

    return update_data


def is_valid_object_id(id):
    return ObjectId.is_valid(id)