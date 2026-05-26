from datetime import datetime, timezone
from bson import ObjectId
from mongo import notifications_collection


# Lấy thời gian hiện tại theo UTC để lưu vào database
# UTC giúp thời gian thống nhất, không bị lệch theo máy người dùng
def _now():
    return datetime.now(timezone.utc)


# Chuyển id dạng chuỗi sang ObjectId của MongoDB
# Nếu id rỗng hoặc sai định dạng thì trả về None
def _to_object_id(value):
    if not value:
        return None

    value = str(value)

    if not ObjectId.is_valid(value):
        return None

    return ObjectId(value)


# Chuyển notification từ MongoDB sang dạng dễ trả về cho frontend
# Đổi _id thành id và đổi datetime thành chuỗi ISO
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


# Tạo một notification mới trong database
# Mặc định notification mới sẽ là chưa đọc
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


# Lấy danh sách notification của một user
# Có thể lấy tất cả hoặc chỉ lấy notification chưa đọc
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


# Đếm số notification chưa đọc của một user
def count_unread_notifications(recipient_user_id):
    return notifications_collection.count_documents({
        "recipient_user_id": str(recipient_user_id),
        "is_read": False
    })


# Đánh dấu một notification là đã đọc
# Nếu truyền recipient_user_id thì chỉ user đó mới được đánh dấu notification này
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


# Đánh dấu toàn bộ notification chưa đọc của một user thành đã đọc
# Trả về số lượng notification đã được cập nhật
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


# Xóa một notification theo id
# Nếu có recipient_user_id thì chỉ xóa notification thuộc về user đó
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
