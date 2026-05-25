from flask import request, jsonify

from templates.notification.notification_service import (
    init_notification_socket,
    send_notification,
    get_user_notifications,
    get_unread_count,
    mark_notification_read,
    mark_all_notifications_read,
    remove_notification
 
)


def _get_bool(value):
    if value is None:
        return False

    return str(value).lower() in ["true", "1", "yes", "y"]


def _get_limit():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    if limit < 1:
        limit = 1

    if limit > 100:
        limit = 100

    return limit


def _get_user_id_from_request():
    return (
        request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or ""
    )


def register_notifications_api_routes(app, socketio=None):
    if socketio:
        init_notification_socket(socketio)

    # Lấy thông báo của chính user đang đăng nhập
    @app.route("/api/notifications/me", methods=["GET"])
    def get_my_notifications():
        user_id = _get_user_id_from_request()

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        only_unread = _get_bool(request.args.get("unread"))
        limit = _get_limit()

        notifications = get_user_notifications(
            user_id=user_id,
            limit=limit,
            only_unread=only_unread
        )

        return jsonify({
            "success": True,
            "data": notifications
        }), 200

    # Đếm số thông báo chưa đọc của chính user đang đăng nhập
    @app.route("/api/notifications/me/unread-count", methods=["GET"])
    def get_my_notifications_unread_count():
        user_id = _get_user_id_from_request()

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu X-User-Id"
            }), 401

        unread_count = get_unread_count(user_id)

        return jsonify({
            "success": True,
            "unread_count": unread_count
        }), 200

    # API lấy notification theo user_id, dùng nội bộ hoặc admin debug
    @app.route("/api/notifications/<user_id>", methods=["GET"])
    def get_notifications(user_id):
        only_unread = _get_bool(request.args.get("unread"))
        limit = _get_limit()

        notifications = get_user_notifications(
            user_id=user_id,
            limit=limit,
            only_unread=only_unread
        )

        return jsonify({
            "success": True,
            "data": notifications
        }), 200

    @app.route("/api/notifications/<user_id>/unread-count", methods=["GET"])
    def get_notifications_unread_count(user_id):
        unread_count = get_unread_count(user_id)

        return jsonify({
            "success": True,
            "unread_count": unread_count
        }), 200

    # Tạo notification thủ công
    @app.route("/api/notifications", methods=["POST"])
    def create_notification_api():
        data = request.get_json(silent=True) or {}

        recipient_user_id = (
            data.get("recipient_user_id")
            or data.get("user_id")
            or data.get("to_user_id")
        )

        title = data.get("title")
        message = data.get("message")
        notification_type = data.get("type", "info")
        extra_data = data.get("data", {})
        created_by = data.get("created_by") or request.headers.get("X-User-Id")

        if not recipient_user_id:
            return jsonify({
                "success": False,
                "message": "recipient_user_id is required"
            }), 400

        if not title:
            return jsonify({
                "success": False,
                "message": "title is required"
            }), 400

        if not message:
            return jsonify({
                "success": False,
                "message": "message is required"
            }), 400

        notification = send_notification(
            recipient_user_id=recipient_user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            data=extra_data,
            created_by=created_by,
            realtime=True
        )

        return jsonify({
            "success": True,
            "message": "Notification created",
            "data": notification
        }), 201

    # Đánh dấu 1 notification là đã đọc
    @app.route("/api/notifications/<notification_id>/read", methods=["PATCH"])
    def mark_notification_read_api(notification_id):
        data = request.get_json(silent=True) or {}

        user_id = (
            data.get("user_id")
            or request.args.get("user_id")
            or request.headers.get("X-User-Id")
        )

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu user_id hoặc X-User-Id"
            }), 401

        notification = mark_notification_read(
            notification_id=notification_id,
            user_id=user_id
        )

        if not notification:
            return jsonify({
                "success": False,
                "message": "Notification not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Notification marked as read",
            "data": notification
        }), 200

    # Đánh dấu toàn bộ notification của user là đã đọc
    @app.route("/api/notifications/read-all", methods=["PATCH"])
    def mark_all_notifications_read_api():
        data = request.get_json(silent=True) or {}

        user_id = (
            data.get("user_id")
            or request.args.get("user_id")
            or request.headers.get("X-User-Id")
        )

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu user_id hoặc X-User-Id"
            }), 401

        modified_count = mark_all_notifications_read(user_id)

        return jsonify({
            "success": True,
            "message": "All notifications marked as read",
            "modified_count": modified_count
        }), 200

    # Xóa notification
    @app.route("/api/notifications/<notification_id>", methods=["DELETE"])
    def delete_notification_api(notification_id):
        data = request.get_json(silent=True) or {}

        user_id = (
            data.get("user_id")
            or request.args.get("user_id")
            or request.headers.get("X-User-Id")
        )

        if not user_id:
            return jsonify({
                "success": False,
                "message": "Thiếu user_id hoặc X-User-Id"
            }), 401

        deleted = remove_notification(
            notification_id=notification_id,
            user_id=user_id
        )

        if not deleted:
            return jsonify({
                "success": False,
                "message": "Notification not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Notification deleted"
        }), 200