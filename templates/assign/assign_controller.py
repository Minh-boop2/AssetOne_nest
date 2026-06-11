from flask import jsonify, request

# Import các hàm gửi thông báo khi cấp phát hoặc thu hồi tài sản.
from templates.notification.notification_service import (
    notify_asset_assigned_by_user,
    notify_asset_unassigned_by_user,
)

# Import các hàm xử lý nghiệp vụ cấp phát tài sản từ service.
from .assign_service import (
    list_assigns,
    find_assign,
    delete_assign,
    approve_assign,
    reject_assign,
    update_assign_status,
)

# Import hàm kiểm tra quyền và lấy user hiện tại từ request.
from templates.permission.permission_service import (
    permission_required,
    get_current_user_from_request,
)

# Import hàm ghi log hoạt động.
from templates.activity.activity_service import create_activity_log


# Lấy id của user hiện tại.
# Nếu user không tồn tại thì trả về chuỗi rỗng để tránh lỗi.
def get_current_user_id(current_user):
    if not current_user:
        return ""

    return str(
        current_user.get("_id")
        or current_user.get("id")
        or current_user.get("user_id")
        or ""
    )


# Lấy tên hiển thị của user hiện tại.
# Ưu tiên full_name, sau đó tới name, email, employee_code.
def get_current_user_name(current_user):
    if not current_user:
        return "Người dùng"

    return (
        current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("email")
        or current_user.get("employee_code")
        or "Người dùng"
    )


# Lấy tên tài sản trong bản ghi cấp phát.
# Nếu thiếu tên thì lấy mã tài sản, cuối cùng dùng chữ mặc định là "tài sản".
def get_assign_asset_name(assign):
    if not assign:
        return "tài sản"

    return (
        assign.get("asset_name")
        or assign.get("asset")
        or assign.get("asset_code")
        or "tài sản"
    )


# Lấy người đang nhận tài sản.
# Có thể lấy từ receiver, user hoặc employee_code.
def get_assign_receiver(assign):
    if not assign:
        return ""

    return (
        assign.get("receiver")
        or assign.get("user")
        or assign.get("employee_code")
        or ""
    )


def parse_bool_arg(name, default=True):
    # NOTE: Cho phép frontend tắt phần nặng như filter_counts khi chỉ reload table.
    raw = request.args.get(name)

    if raw is None:
        return default

    return str(raw).strip().lower() not in ["0", "false", "no", "off"]


# Gom thông tin cấp phát thành metadata để lưu vào log hoạt động.
# Metadata giúp xem lại trước đó thao tác đã tác động tới tài sản nào.
def build_assign_metadata(assign):
    if not assign:
        return {}

    return {
        "assign_id": assign.get("id") or assign.get("mongo_id"),
        "mongo_id": assign.get("mongo_id"),
        "asset_code": assign.get("asset_code"),
        "asset_name": assign.get("asset_name") or assign.get("asset"),
        "type": assign.get("type") or assign.get("category"),
        "category": assign.get("category") or assign.get("type"),
        "status": assign.get("status"),
        "asset_status": assign.get("asset_status"),
        "user_id": assign.get("user_id"),
        "employee_code": assign.get("employee_code"),
        "receiver": assign.get("receiver") or assign.get("user"),
        "department": assign.get("department"),
        "location": assign.get("location"),
        "date": assign.get("date"),
        "return_date": assign.get("return_date"),
        "assigned_at": assign.get("assigned_at"),
        "returned_at": assign.get("returned_at"),
    }


# Ghi log cho các thao tác liên quan tới cấp phát tài sản.
# Bọc try/except để lỗi log không làm hỏng API chính.
def log_assign_activity(
    current_user,
    action,
    method,
    status_code,
    target_id=None,
    target_name=None,
    metadata=None,
):
    try:
        current_user_id = get_current_user_id(current_user)

        # Không có user id thì không ghi log.
        if not current_user_id:
            return

        create_activity_log(
            user_id=current_user_id,
            action=action,
            module="assign",
            method=method,
            path=request.path,
            status_code=status_code,
            target_id=target_id,
            target_name=target_name,
            metadata=metadata or {},
        )

    except Exception:
        # Không để lỗi ghi log làm hỏng API chính.
        pass


# Gửi thông báo khi duyệt cấp phát tài sản thành công.
# Nếu không có bản ghi cấp phát thì bỏ qua.
def notify_assign_approved(current_user, assign):
    try:
        if not assign:
            return

        notify_asset_assigned_by_user(
            actor_user=current_user,
            asset=assign,
        )

    except Exception:
        # Không để lỗi notification làm hỏng API chính.
        pass


# Gửi thông báo khi từ chối cấp phát hoặc thu hồi tài sản.
# old_receiver dùng để biết trước đó ai đang giữ tài sản.
def notify_assign_rejected_or_unassigned(current_user, assign, old_receiver=None):
    try:
        if not assign:
            return

        notify_asset_unassigned_by_user(
            actor_user=current_user,
            asset=assign,
            old_receiver=old_receiver,
        )

    except Exception:
        # Không để lỗi notification làm hỏng API chính.
        pass


# Tự chọn loại notification theo status mới.
# Đang sử dụng => thông báo cấp phát.
# Chưa dùng / Chưa sử dụng => thông báo thu hồi.
def notify_assign_status_changed(current_user, old_assign, item, status):
    status = (status or "").strip()

    try:
        if status == "Đang sử dụng":
            notify_assign_approved(
                current_user=current_user,
                assign=item or old_assign,
            )
            return

        if status in ["Chưa dùng", "Chưa sử dụng"]:
            notify_assign_rejected_or_unassigned(
                current_user=current_user,
                assign=item or old_assign,
                old_receiver=get_assign_receiver(old_assign),
            )
            return

    except Exception:
        # Không để lỗi notification làm hỏng API chính.
        pass


# Tạo nội dung log khi duyệt cấp phát tài sản.
def build_approve_action(assign, current_user=None):
    actor_name = get_current_user_name(current_user)
    asset_name = get_assign_asset_name(assign)
    receiver = get_assign_receiver(assign)

    if receiver:
        return f"{actor_name} duyệt cấp phát {asset_name} cho {receiver}"

    return f"{actor_name} duyệt cấp phát {asset_name}"


# Tạo nội dung log khi từ chối hoặc hủy cấp phát tài sản.
def build_reject_action(assign, current_user=None):
    actor_name = get_current_user_name(current_user)
    asset_name = get_assign_asset_name(assign)
    receiver = get_assign_receiver(assign)

    if receiver:
        return f"{actor_name} từ chối / hủy cấp phát {asset_name} của {receiver}"

    return f"{actor_name} từ chối / hủy cấp phát {asset_name}"


# Tạo nội dung log khi cập nhật trạng thái cấp phát.
# Nội dung sẽ đổi theo status mới để dễ đọc lịch sử hoạt động.
def build_update_status_action(assign, status, current_user=None):
    actor_name = get_current_user_name(current_user)
    asset_name = get_assign_asset_name(assign)
    receiver = get_assign_receiver(assign)

    if status in ["Chưa dùng", "Chưa sử dụng"]:
        if receiver:
            return f"{actor_name} thu hồi {asset_name} từ {receiver}"

        return f"{actor_name} thu hồi {asset_name}"

    if status == "Đang sử dụng":
        if receiver:
            return f"{actor_name} cập nhật cấp phát {asset_name} cho {receiver}"

        return f"{actor_name} cập nhật cấp phát {asset_name}"

    return f"{actor_name} cập nhật trạng thái cấp phát {asset_name} thành {status}"


# Đăng ký tất cả API route cho module cấp phát tài sản.
def register_assign_api_routes(app):

    # API lấy danh sách cấp phát tài sản.
    # Có phân trang, tìm kiếm và lọc theo loại, phòng ban, trạng thái, vị trí.
    @app.route("/api/assign", methods=["GET"])
    @permission_required("assign", "view")
    def assigns_api():
        current_user = get_current_user_from_request()

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        search = request.args.get("search", "", type=str).strip()

        asset_type = request.args.get("type", "Tất cả", type=str)
        department = request.args.get("department", "Tất cả", type=str)
        status = request.args.get("status", "Tất cả", type=str)
        location = request.args.get("location", "Tất cả", type=str)

        return jsonify(
            list_assigns(
                page=page,
                per_page=per_page,
                search=search,
                asset_type=asset_type,
                department=department,
                status=status,
                location=location,
                current_user=current_user,
                # NOTE: Mặc định vẫn giữ logic cũ là có counts.
                # Chỉ khi /assign fetch table gửi include_counts=0 thì mới bỏ qua.
                include_counts=parse_bool_arg("include_counts", True),
            )
        ), 200

    # API lấy chi tiết một bản ghi cấp phát theo id.
    @app.route("/api/assign/<string:assign_id>", methods=["GET"])
    @permission_required("assign", "view")
    def get_assign_detail_api(assign_id):
        current_user = get_current_user_from_request()

        assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        if not assign:
            return jsonify({
                "message": "Assign not found"
            }), 404

        return jsonify(assign), 200

    # API xóa một bản ghi cấp phát tài sản.
    # Sau khi xóa thành công sẽ ghi log hoạt động.
    @app.route("/api/assign/<string:assign_id>", methods=["DELETE"])
    @permission_required("assign", "delete")
    def delete_assign_api(assign_id):
        current_user = get_current_user_from_request()

        # Lấy dữ liệu cũ trước khi xóa để còn ghi log.
        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        if not old_assign:
            return jsonify({
                "message": "Assign not found"
            }), 404

        result = delete_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["deleted"]:
            return jsonify({
                "message": "Assign not found"
            }), 404

        asset_name = get_assign_asset_name(old_assign)
        receiver = get_assign_receiver(old_assign)
        actor_name = get_current_user_name(current_user)

        if receiver:
            action = f"{actor_name} xóa bản ghi cấp phát {asset_name} của {receiver}"
        else:
            action = f"{actor_name} xóa bản ghi cấp phát {asset_name}"

        log_assign_activity(
            current_user=current_user,
            action=action,
            method=request.method,
            status_code=200,
            target_id=old_assign.get("id") or assign_id,
            target_name=asset_name,
            metadata=build_assign_metadata(old_assign),
        )

        return jsonify({
            "message": "Assign deleted successfully",
            "assign_id": assign_id,
            "deleted_count": result["deleted_count"],
        }), 200

    # API duyệt cấp phát tài sản.
    # Khi duyệt thành công, trạng thái tài sản sẽ chuyển sang đang sử dụng.
    @app.route("/api/assign/<string:assign_id>/approve", methods=["PATCH", "POST"])
    @permission_required("assign", "approve")
    def assign_approve_api(assign_id):
        current_user = get_current_user_from_request()

        # Lấy dữ liệu trước khi duyệt để lưu vào log phần before.
        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        result = approve_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": result.get("message") or "Assign not found"
            }), result.get("status_code", 404)

        item = result.get("item") or old_assign or {}
        asset_name = get_assign_asset_name(item)

        log_assign_activity(
            current_user=current_user,
            action=build_approve_action(item, current_user=current_user),
            method=request.method,
            status_code=200,
            target_id=item.get("id") or assign_id,
            target_name=asset_name,
            metadata={
                "before": build_assign_metadata(old_assign),
                "after": build_assign_metadata(item),
            },
        )

        # Gửi notification realtime cho ADMIN + QUAN_LY.
        # NHAN_VIEN không nhận notification loại này.
        notify_assign_approved(
            current_user=current_user,
            assign=item,
        )

        return jsonify({
            "message": "Assign approved successfully",
            "assign_id": assign_id,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200

    # API từ chối hoặc hủy cấp phát tài sản.
    # Khi xử lý thành công, tài sản sẽ quay về trạng thái chưa dùng.
    @app.route("/api/assign/<string:assign_id>/reject", methods=["PATCH", "POST"])
    @permission_required("assign", "approve")
    def assign_reject_api(assign_id):
        current_user = get_current_user_from_request()

        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        old_receiver = get_assign_receiver(old_assign)

        result = reject_assign(
            assign_id,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": result.get("message") or "Assign not found"
            }), result.get("status_code", 404)

        item = result.get("item") or old_assign or {}
        asset_name = get_assign_asset_name(item)

        log_assign_activity(
            current_user=current_user,
            action=build_reject_action(old_assign or item, current_user=current_user),
            method=request.method,
            status_code=200,
            target_id=(old_assign or item).get("id") or assign_id,
            target_name=asset_name,
            metadata={
                "before": build_assign_metadata(old_assign),
                "after": build_assign_metadata(item),
            },
        )

        # Gửi notification realtime cho ADMIN + QUAN_LY.
        # NHAN_VIEN không nhận notification loại này.
        notify_assign_rejected_or_unassigned(
            current_user=current_user,
            assign=item,
            old_receiver=old_receiver,
        )

        return jsonify({
            "message": "Assign rejected successfully",
            "assign_id": assign_id,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200

    # API cập nhật trạng thái cấp phát.
    # Ví dụ: chuyển sang Đang sử dụng hoặc Chưa dùng.
    @app.route("/api/assign/<string:assign_id>/status", methods=["PATCH"])
    @permission_required("assign", "update")
    def assign_update_status_api(assign_id):
        current_user = get_current_user_from_request()

        body = request.get_json(silent=True) or {}
        status = body.get("status")

        if not status:
            return jsonify({
                "message": "Missing status"
            }), 400

        # Lấy dữ liệu cũ trước khi cập nhật để ghi log so sánh before / after.
        old_assign = find_assign(
            assign_id,
            current_user=current_user,
        )

        old_receiver = get_assign_receiver(old_assign)

        result = update_assign_status(
            assign_id,
            status,
            current_user=current_user,
        )

        if not result["updated"]:
            return jsonify({
                "message": result.get("message") or "Assign not found"
            }), result.get("status_code", 404)

        item = result.get("item") or old_assign or {}
        asset_name = get_assign_asset_name(item or old_assign)

        log_assign_activity(
            current_user=current_user,
            action=build_update_status_action(
                old_assign or item,
                status,
                current_user=current_user,
            ),
            method=request.method,
            status_code=200,
            target_id=(old_assign or item).get("id") or assign_id,
            target_name=asset_name,
            metadata={
                "status": status,
                "before": build_assign_metadata(old_assign),
                "after": build_assign_metadata(item),
            },
        )

        # Nếu status là Đang sử dụng => thông báo cấp phát.
        # Nếu status là Chưa dùng / Chưa sử dụng => thông báo thu hồi.
        # Các thông báo này chỉ gửi ADMIN + QUAN_LY.
        notify_assign_status_changed(
            current_user=current_user,
            old_assign=old_assign,
            item=item,
            status=status,
        )

        return jsonify({
            "message": "Assign status updated successfully",
            "assign_id": assign_id,
            "status": status,
            "modified_count": result["modified_count"],
            "item": result["item"],
        }), 200