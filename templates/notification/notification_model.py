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


# Chuyển datetime thành chuỗi ISO để frontend dễ xử lý
def _datetime_to_iso(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return value


# Chuẩn hóa danh sách user_id để lưu và query thống nhất
def _normalize_user_ids(user_ids):
    if not user_ids:
        return []

    if not isinstance(user_ids, list):
        user_ids = [user_ids]

    result = []

    for user_id in user_ids:
        if user_id is None:
            continue

        user_id = str(user_id).strip()

        if user_id and user_id not in result:
            result.append(user_id)

    return result


# Chuẩn hóa role để lưu và query thống nhất
def _normalize_roles(roles):
    if not roles:
        return []

    if not isinstance(roles, list):
        roles = [roles]

    result = []

    for role in roles:
        if role is None:
            continue

        role = str(role).strip().upper()

        if role and role not in result:
            result.append(role)

    return result


# Lấy thời gian đọc notification dùng chung của một user
def _get_shared_read_at(notification, user_id):
    user_id = str(user_id)

    for item in notification.get("read_logs", []):
        if str(item.get("user_id")) == user_id:
            return item.get("read_at")

    return None


# Tạo query lấy notification mà user hiện tại được phép xem
def _build_visible_query(user_id, user_role=None, only_unread=False):
    user_id = str(user_id)
    user_role = str(user_role).strip().upper() if user_role else None

    conditions = []

    if only_unread:
        conditions.append({
            "recipient_user_id": user_id,
            "is_read": False
        })

        conditions.append({
            "audience_user_ids": user_id,
            "read_by_user_ids": {
                "$ne": user_id
            }
        })

        if user_role:
            conditions.append({
                "audience_roles": user_role,
                "read_by_user_ids": {
                    "$ne": user_id
                }
            })
    else:
        conditions.append({
            "recipient_user_id": user_id
        })

        conditions.append({
            "audience_user_ids": user_id
        })

        if user_role:
            conditions.append({
                "audience_roles": user_role
            })

    return {
        "deleted_by_user_ids": {
            "$ne": user_id
        },
        "$or": conditions
    }


# Chuyển notification từ MongoDB sang dạng dễ trả về cho frontend
# Đổi _id thành id và đổi datetime thành chuỗi ISO
def serialize_notification(notification, viewer_user_id=None):
    if not notification:
        return None

    notification = dict(notification)
    viewer_user_id = str(viewer_user_id) if viewer_user_id else None

    notification["id"] = str(notification["_id"])
    del notification["_id"]

    # Nếu là notification dùng chung thì trạng thái đọc được tính riêng theo user đang xem
    if viewer_user_id and notification.get("recipient_user_id") != viewer_user_id:
        notification["is_read"] = viewer_user_id in notification.get("read_by_user_ids", [])
        notification["read_at"] = _get_shared_read_at(notification, viewer_user_id)

    if isinstance(notification.get("created_at"), datetime):
        notification["created_at"] = notification["created_at"].isoformat()

    if isinstance(notification.get("read_at"), datetime):
        notification["read_at"] = notification["read_at"].isoformat()

    # Các field nội bộ dùng để xử lý shared notification, không cần trả hết cho frontend
    notification.pop("read_by_user_ids", None)
    notification.pop("deleted_by_user_ids", None)
    notification.pop("read_logs", None)
    notification.pop("audience_user_ids", None)

    return notification


# Tạo một notification mới trong database
# Mặc định notification mới sẽ là chưa đọc
def create_notification(
    recipient_user_id,
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None,
    audience_user_ids=None,
    audience_roles=None
):
    audience_user_ids = _normalize_user_ids(audience_user_ids)
    audience_roles = _normalize_roles(audience_roles)

    notification = {
        "recipient_user_id": str(recipient_user_id) if recipient_user_id else None,
        "audience_user_ids": audience_user_ids,
        "audience_roles": audience_roles,
        "audience_type": "shared" if audience_user_ids or audience_roles else "single",
        "title": title,
        "message": message,
        "type": notification_type,
        "data": data or {},
        "is_read": False,
        "read_by_user_ids": [],
        "deleted_by_user_ids": [],
        "read_logs": [],
        "created_by": str(created_by) if created_by else None,
        "created_at": _now(),
        "read_at": None
    }

    result = notifications_collection.insert_one(notification)
    notification["_id"] = result.inserted_id

    return serialize_notification(notification)


# Tạo một notification dùng chung cho nhiều user hoặc nhiều role
# Database chỉ lưu 1 document, user đủ điều kiện mới nhìn thấy
def create_shared_notification(
    recipient_user_ids=None,
    audience_roles=None,
    title=None,
    message=None,
    notification_type="info",
    data=None,
    created_by=None
):
    recipient_user_ids = _normalize_user_ids(recipient_user_ids)
    audience_roles = _normalize_roles(audience_roles)

    if not recipient_user_ids and not audience_roles:
        return None

    return create_notification(
        recipient_user_id=None,
        title=title,
        message=message,
        notification_type=notification_type,
        data=data,
        created_by=created_by,
        audience_user_ids=recipient_user_ids,
        audience_roles=audience_roles
    )


# Lấy danh sách notification của một user
# Có thể lấy tất cả hoặc chỉ lấy notification chưa đọc
def get_notifications_by_user(recipient_user_id, limit=50, only_unread=False, user_role=None):
    query = _build_visible_query(
        user_id=recipient_user_id,
        user_role=user_role,
        only_unread=only_unread
    )

    notifications = (
        notifications_collection
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
    )

    return [
        serialize_notification(item, viewer_user_id=recipient_user_id)
        for item in notifications
    ]


# Đếm số notification chưa đọc của một user
def count_unread_notifications(recipient_user_id, user_role=None):
    query = _build_visible_query(
        user_id=recipient_user_id,
        user_role=user_role,
        only_unread=True
    )

    return notifications_collection.count_documents(query)


# Đánh dấu shared notification là đã đọc riêng cho một user
def _mark_shared_notification_as_read(notification_id, recipient_user_id):
    now = _now()
    recipient_user_id = str(recipient_user_id)

    notifications_collection.update_one(
        {
            "_id": notification_id,
            "read_by_user_ids": {
                "$ne": recipient_user_id
            }
        },
        {
            "$addToSet": {
                "read_by_user_ids": recipient_user_id
            },
            "$push": {
                "read_logs": {
                    "user_id": recipient_user_id,
                    "read_at": now
                }
            }
        }
    )


# Đánh dấu một notification là đã đọc
# Nếu truyền recipient_user_id thì chỉ user đó mới được đánh dấu notification này
def mark_notification_as_read(notification_id, recipient_user_id=None, user_role=None):
    object_id = _to_object_id(notification_id)

    if not object_id:
        return None

    if not recipient_user_id:
        notifications_collection.update_one(
            {
                "_id": object_id
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": _now()
                }
            }
        )

        notification = notifications_collection.find_one({
            "_id": object_id
        })

        return serialize_notification(notification)

    query = _build_visible_query(
        user_id=recipient_user_id,
        user_role=user_role
    )
    query["_id"] = object_id

    notification = notifications_collection.find_one(query)

    if not notification:
        return None

    if notification.get("recipient_user_id") == str(recipient_user_id):
        notifications_collection.update_one(
            {
                "_id": object_id,
                "recipient_user_id": str(recipient_user_id)
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": _now()
                }
            }
        )
    else:
        _mark_shared_notification_as_read(
            notification_id=object_id,
            recipient_user_id=recipient_user_id
        )

    notification = notifications_collection.find_one({
        "_id": object_id
    })

    return serialize_notification(notification, viewer_user_id=recipient_user_id)


# Đánh dấu toàn bộ notification chưa đọc của một user thành đã đọc
# Trả về số lượng notification đã được cập nhật
def mark_all_notifications_as_read(recipient_user_id, user_role=None):
    recipient_user_id = str(recipient_user_id)
    user_role = str(user_role).strip().upper() if user_role else None
    now = _now()

    personal_result = notifications_collection.update_many(
        {
            "recipient_user_id": recipient_user_id,
            "is_read": False,
            "deleted_by_user_ids": {
                "$ne": recipient_user_id
            }
        },
        {
            "$set": {
                "is_read": True,
                "read_at": now
            }
        }
    )

    shared_conditions = [
        {
            "audience_user_ids": recipient_user_id
        }
    ]

    if user_role:
        shared_conditions.append({
            "audience_roles": user_role
        })

    shared_query = {
        "deleted_by_user_ids": {
            "$ne": recipient_user_id
        },
        "read_by_user_ids": {
            "$ne": recipient_user_id
        },
        "$or": shared_conditions
    }

    shared_notifications = list(
        notifications_collection.find(
            shared_query,
            {
                "_id": 1
            }
        )
    )

    for notification in shared_notifications:
        _mark_shared_notification_as_read(
            notification_id=notification["_id"],
            recipient_user_id=recipient_user_id
        )

    return personal_result.modified_count + len(shared_notifications)


# Xóa một notification theo id
# Nếu có recipient_user_id thì chỉ xóa notification thuộc về user đó
def delete_notification(notification_id, recipient_user_id=None, user_role=None):
    object_id = _to_object_id(notification_id)

    if not object_id:
        return False

    if not recipient_user_id:
        result = notifications_collection.delete_one({
            "_id": object_id
        })

        return result.deleted_count > 0

    query = _build_visible_query(
        user_id=recipient_user_id,
        user_role=user_role
    )
    query["_id"] = object_id

    notification = notifications_collection.find_one(query)

    if not notification:
        return False

    if notification.get("recipient_user_id") == str(recipient_user_id):
        result = notifications_collection.delete_one({
            "_id": object_id,
            "recipient_user_id": str(recipient_user_id)
        })

        return result.deleted_count > 0

    result = notifications_collection.update_one(
        {
            "_id": object_id
        },
        {
            "$addToSet": {
                "deleted_by_user_ids": str(recipient_user_id)
            }
        }
    )

    return result.modified_count > 0