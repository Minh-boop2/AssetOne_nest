# File xử lý logic notification
# Bao gồm lưu notification, gửi realtime qua socket và gửi cho từng nhóm user

from flask_socketio import join_room, leave_room, emit

from templates.notification.notification_model import (
    create_notification,
    get_notifications_by_user,
    count_unread_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    delete_notification
)

from templates.user.user_service import (
    get_admin_and_manager_users,
    get_admin_users,
    get_manager_users
)


_socketio = None
_socket_initialized = False


# Tạo tên phòng socket riêng cho từng user
# Mỗi user sẽ nhận notification trong phòng riêng của mình
def get_user_notification_room(user_id):
    return f"notifications:user:{str(user_id)}"


# Khởi tạo socket notification
# Hàm này đăng ký các sự kiện realtime như join, leave, mark read
def init_notification_socket(socketio):
    global _socketio, _socket_initialized

    _socketio = socketio

    if _socket_initialized:
        return

    _socket_initialized = True

    @socketio.on("join_notifications")
    # User tham gia phòng notification của chính họ
    def handle_join_notifications(data):
        data = data or {}
        user_id = data.get("user_id")

        if not user_id:
            emit("notification:error", {
                "message": "user_id is required"
            })
            return

        room = get_user_notification_room(user_id)
        join_room(room)

        emit("notifications:joined", {
            "user_id": str(user_id),
            "room": room,
            "unread_count": count_unread_notifications(user_id)
        })

    @socketio.on("leave_notifications")
    # User rời khỏi phòng notification của chính họ
    def handle_leave_notifications(data):
        data = data or {}
        user_id = data.get("user_id")

        if not user_id:
            emit("notification:error", {
                "message": "user_id is required"
            })
            return

        room = get_user_notification_room(user_id)
        leave_room(room)

        emit("notifications:left", {
            "user_id": str(user_id),
            "room": room
        })

    @socketio.on("notification:mark_read")
    # Đánh dấu một notification đã đọc thông qua socket
    def handle_socket_mark_read(data):
        data = data or {}

        user_id = data.get("user_id")
        notification_id = data.get("notification_id")

        if not user_id or not notification_id:
            emit("notification:error", {
                "message": "user_id and notification_id are required"
            })
            return

        notification = mark_notification_read(notification_id, user_id)

        if not notification:
            emit("notification:error", {
                "message": "Notification not found"
            })
            return

    @socketio.on("notifications:mark_all_read")
    # Đánh dấu toàn bộ notification đã đọc thông qua socket
    def handle_socket_mark_all_read(data):
        data = data or {}
        user_id = data.get("user_id")

        if not user_id:
            emit("notification:error", {
                "message": "user_id is required"
            })
            return

        mark_all_notifications_read(user_id)


# Gửi một sự kiện realtime tới đúng phòng notification của user
def emit_to_user(user_id, event_name, payload):
    if not _socketio:
        return

    room = get_user_notification_room(user_id)

    _socketio.emit(
        event_name,
        payload,
        room=room
    )


# Tạo notification mới và gửi realtime nếu được bật
def send_notification(
    recipient_user_id,
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None,
    realtime=True
):
    notification = create_notification(
        recipient_user_id=recipient_user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        data=data,
        created_by=created_by
    )

    unread_count = count_unread_notifications(recipient_user_id)

    if realtime:
        emit_to_user(recipient_user_id, "notification:new", {
            "notification": notification,
            "unread_count": unread_count
        })

    return notification


# Lấy danh sách notification của một user từ model
def get_user_notifications(user_id, limit=50, only_unread=False):
    return get_notifications_by_user(
        recipient_user_id=user_id,
        limit=limit,
        only_unread=only_unread
    )


# Lấy số lượng notification chưa đọc của một user
def get_unread_count(user_id):
    return count_unread_notifications(user_id)


# Đánh dấu một notification là đã đọc
# Sau đó bắn realtime để frontend cập nhật lại giao diện
def mark_notification_read(notification_id, user_id=None):
    notification = mark_notification_as_read(
        notification_id=notification_id,
        recipient_user_id=user_id
    )

    if notification and user_id:
        emit_to_user(user_id, "notification:read", {
            "notification": notification,
            "unread_count": count_unread_notifications(user_id)
        })

    return notification


# Đánh dấu tất cả notification của user là đã đọc
# Sau đó báo frontend cập nhật unread_count về 0
def mark_all_notifications_read(user_id):
    modified_count = mark_all_notifications_as_read(user_id)

    emit_to_user(user_id, "notifications:read_all", {
        "user_id": str(user_id),
        "modified_count": modified_count,
        "unread_count": 0
    })

    return modified_count


# Xóa notification và gửi realtime báo frontend xóa khỏi danh sách
def remove_notification(notification_id, user_id=None):
    deleted = delete_notification(
        notification_id=notification_id,
        recipient_user_id=user_id
    )

    if deleted and user_id:
        emit_to_user(user_id, "notification:deleted", {
            "notification_id": str(notification_id),
            "unread_count": count_unread_notifications(user_id)
        })

    return deleted


# Gửi cùng một notification cho nhiều user
def send_notification_to_users(
    users,
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None
):
    notifications = []

    for user in users:
        user_id = user.get("id") or user.get("_id")

        if not user_id:
            continue

        notification = send_notification(
            recipient_user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            data=data,
            created_by=created_by
        )

        notifications.append(notification)

    return notifications


# Gửi notification cho toàn bộ ADMIN và QUAN_LY
def notify_admins_and_managers(
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None
):
    users = get_admin_and_manager_users()

    return send_notification_to_users(
        users=users,
        title=title,
        message=message,
        notification_type=notification_type,
        data=data,
        created_by=created_by
    )


# Gửi notification cho toàn bộ ADMIN
def notify_admins(
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None
):
    users = get_admin_users()

    return send_notification_to_users(
        users=users,
        title=title,
        message=message,
        notification_type=notification_type,
        data=data,
        created_by=created_by
    )


# Gửi notification cho toàn bộ QUAN_LY
def notify_managers(
    title,
    message,
    notification_type="info",
    data=None,
    created_by=None
):
    users = get_manager_users()

    return send_notification_to_users(
        users=users,
        title=title,
        message=message,
        notification_type=notification_type,
        data=data,
        created_by=created_by
    )


# Thông báo cho ADMIN và QUAN_LY khi nhân viên tạo báo cáo mới
def notify_staff_report_created(
    staff_user_id,
    staff_name=None,
    report_id=None,
    report_title=None,
    report_type=None,
    asset_name=None
):
    name = staff_name or "Nhân viên"
    title_report = report_title or "báo cáo"

    return notify_admins_and_managers(
        title="Có báo cáo mới từ nhân viên",
        message=f"{name} vừa gửi {title_report}.",
        notification_type="staff_report_created",
        data={
            "staff_user_id": str(staff_user_id) if staff_user_id else None,
            "staff_name": staff_name,
            "report_id": str(report_id) if report_id else None,
            "report_title": report_title,
            "report_type": report_type,
            "asset_name": asset_name,
            "status": "pending"
        },
        created_by=staff_user_id
    )


# Thông báo cho nhân viên khi báo cáo của họ được duyệt
def notify_report_approved(
    recipient_user_id,
    report_id=None,
    report_title=None,
    approved_by=None,
    approval_note=None
):
    report_name = report_title or "Báo cáo"

    return send_notification(
        recipient_user_id=recipient_user_id,
        title="Báo cáo đã được duyệt",
        message=f"{report_name} của bạn đã được duyệt.",
        notification_type="report_approved",
        data={
            "report_id": str(report_id) if report_id else None,
            "report_title": report_title,
            "approval_note": approval_note,
            "status": "approved"
        },
        created_by=approved_by
    )


# Thông báo cho nhân viên khi báo cáo của họ bị hủy
def notify_report_cancelled(
    recipient_user_id,
    report_id=None,
    report_title=None,
    cancelled_by=None,
    reason=None
):
    report_name = report_title or "Báo cáo"

    message = f"{report_name} của bạn đã bị hủy."

    if reason:
        message += f" Lý do: {reason}"

    return send_notification(
        recipient_user_id=recipient_user_id,
        title="Báo cáo đã bị hủy",
        message=message,
        notification_type="report_cancelled",
        data={
            "report_id": str(report_id) if report_id else None,
            "report_title": report_title,
            "reason": reason,
            "status": "cancelled"
        },
        created_by=cancelled_by
    )


# Thông báo cho nhân viên khi báo cáo của họ bị từ chối
def notify_report_rejected(
    recipient_user_id,
    report_id=None,
    report_title=None,
    rejected_by=None,
    reason=None
):
    report_name = report_title or "Báo cáo"

    message = f"{report_name} của bạn đã bị từ chối."

    if reason:
        message += f" Lý do: {reason}"

    return send_notification(
        recipient_user_id=recipient_user_id,
        title="Báo cáo bị từ chối",
        message=message,
        notification_type="report_rejected",
        data={
            "report_id": str(report_id) if report_id else None,
            "report_title": report_title,
            "reason": reason,
            "status": "rejected"
        },
        created_by=rejected_by
    )


# Thông báo cho nhân viên khi họ được cấp phát tài sản
def notify_staff_asset_assigned(
    recipient_user_id,
    asset_id=None,
    asset_name=None,
    assigned_by=None
):
    name = asset_name or "tài sản"

    return send_notification(
        recipient_user_id=recipient_user_id,
        title="Bạn được cấp phát tài sản",
        message=f"Bạn vừa được cấp phát {name}.",
        notification_type="asset_assigned",
        data={
            "asset_id": str(asset_id) if asset_id else None,
            "asset_name": asset_name,
            "status": "assigned"
        },
        created_by=assigned_by
    )


# Thông báo cho nhân viên khi tài sản của họ bị thu hồi
def notify_staff_asset_revoked(
    recipient_user_id,
    asset_id=None,
    asset_name=None,
    revoked_by=None
):
    name = asset_name or "tài sản"

    return send_notification(
        recipient_user_id=recipient_user_id,
        title="Tài sản đã bị thu hồi",
        message=f"{name} của bạn đã được thu hồi.",
        notification_type="asset_revoked",
        data={
            "asset_id": str(asset_id) if asset_id else None,
            "asset_name": asset_name,
            "status": "revoked"
        },
        created_by=revoked_by
    )
# Lấy id của người đang thực hiện hành động
def _get_actor_id(actor_user):
    if not actor_user:
        return None

    return str(
        actor_user.get("_id")
        or actor_user.get("id")
        or actor_user.get("user_id")
        or ""
    )


# Lấy tên hiển thị của người đang thực hiện hành động
def _get_actor_name(actor_user):
    if not actor_user:
        return "Người dùng"

    return (
        actor_user.get("full_name")
        or actor_user.get("name")
        or actor_user.get("email")
        or actor_user.get("employee_code")
        or "Người dùng"
    )


# Lấy id tài sản, nếu không có thì dùng asset_code
def _get_asset_id(asset):
    if not asset:
        return None

    return str(
        asset.get("id")
        or asset.get("_id")
        or asset.get("asset_code")
        or ""
    )


# Lấy tên tài sản để đưa vào nội dung notification
def _get_asset_name(asset):
    if not asset:
        return "tài sản"

    return (
        asset.get("asset_name")
        or asset.get("asset")
        or asset.get("asset_code")
        or "tài sản"
    )


# Lấy mã tài sản
def _get_asset_code(asset):
    if not asset:
        return ""

    return asset.get("asset_code") or ""


# Lấy tên hoặc mã nhân viên của người nhận tài sản
def _get_asset_receiver(asset):
    if not asset:
        return ""

    return (
        asset.get("receiver")
        or asset.get("user")
        or asset.get("employee_code")
        or ""
    )


# Thông báo cho ADMIN và QUAN_LY khi có tài sản mới được tạo
def notify_asset_created_by_user(actor_user, asset):
    actor_id = _get_actor_id(actor_user)
    actor_name = _get_actor_name(actor_user)
    asset_name = _get_asset_name(asset)
    asset_code = _get_asset_code(asset)

    return notify_admins_and_managers(
        title="Có tài sản mới được tạo",
        message=f"{actor_name} đã tạo tài sản mới: {asset_name}.",
        notification_type="asset_created",
        data={
            "asset_id": _get_asset_id(asset),
            "asset_code": asset_code,
            "asset_name": asset_name,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "action": "created",
            "visible_for_roles": ["ADMIN", "QUAN_LY"],
        },
        created_by=actor_id,
    )


# Thông báo cho ADMIN và QUAN_LY khi tạo nhiều tài sản cùng lúc
def notify_assets_bulk_created_by_user(actor_user, inserted_count, assets=None):
    actor_id = _get_actor_id(actor_user)
    actor_name = _get_actor_name(actor_user)
    assets = assets or []

    return notify_admins_and_managers(
        title="Có nhiều tài sản mới được tạo",
        message=f"{actor_name} đã tạo mới {inserted_count} tài sản.",
        notification_type="assets_bulk_created",
        data={
            "inserted_count": inserted_count,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "asset_ids": [
                _get_asset_id(asset)
                for asset in assets
                if _get_asset_id(asset)
            ],
            "asset_codes": [
                _get_asset_code(asset)
                for asset in assets
                if _get_asset_code(asset)
            ],
            "action": "bulk_created",
            "visible_for_roles": ["ADMIN", "QUAN_LY"],
        },
        created_by=actor_id,
    )


# Thông báo cho ADMIN và QUAN_LY khi tài sản được cấp phát
def notify_asset_assigned_by_user(actor_user, asset):
    actor_id = _get_actor_id(actor_user)
    actor_name = _get_actor_name(actor_user)
    asset_name = _get_asset_name(asset)
    asset_code = _get_asset_code(asset)
    receiver = _get_asset_receiver(asset)

    return notify_admins_and_managers(
        title="Tài sản vừa được cấp phát",
        message=f"{actor_name} đã cấp phát {asset_name} cho {receiver}.",
        notification_type="asset_assigned_admin",
        data={
            "asset_id": _get_asset_id(asset),
            "asset_code": asset_code,
            "asset_name": asset_name,
            "receiver_user_id": asset.get("user_id") if asset else "",
            "receiver_employee_code": asset.get("employee_code") if asset else "",
            "receiver_name": receiver,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "action": "assigned",
            "visible_for_roles": ["ADMIN", "QUAN_LY"],
        },
        created_by=actor_id,
    )


# Thông báo cho ADMIN và QUAN_LY khi tài sản được thu hồi
def notify_asset_unassigned_by_user(actor_user, asset, old_receiver=None):
    actor_id = _get_actor_id(actor_user)
    actor_name = _get_actor_name(actor_user)
    asset_name = _get_asset_name(asset)
    asset_code = _get_asset_code(asset)
    receiver = old_receiver or "người dùng"

    return notify_admins_and_managers(
        title="Tài sản vừa được thu hồi",
        message=f"{actor_name} đã thu hồi {asset_name} từ {receiver}.",
        notification_type="asset_unassigned_admin",
        data={
            "asset_id": _get_asset_id(asset),
            "asset_code": asset_code,
            "asset_name": asset_name,
            "old_receiver_name": receiver,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "action": "unassigned",
            "visible_for_roles": ["ADMIN", "QUAN_LY"],
        },
        created_by=actor_id,
    )
