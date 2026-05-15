from functools import wraps
from bson import ObjectId
from flask import request, jsonify

from mongo import users_collection, permissions_collection

from templates.permission.permission_model import (
    ADMIN_ROLE,
    VALID_PERMISSION_ROLES,
    PERMISSION_MODULES,
    DEFAULT_ROLE_PERMISSIONS,
    permission_serializer,
    create_permission_model,
    update_permission_model,
    normalize_permissions,
    is_valid_permission,
)


def ensure_permission_indexes():
    try:
        permissions_collection.create_index("role", unique=True)
    except Exception:
        pass


ensure_permission_indexes()


def get_current_user_from_request():
    """
    Lấy user hiện tại từ request.

    Hiện tại login của bạn trả về data user có id.
    Frontend chỉ cần gửi kèm header:

    X-User-Id: user_id

    Hoặc có thể gửi query/body:
    ?current_user_id=...
    {
        "current_user_id": "..."
    }
    """

    user_id = request.headers.get("X-User-Id")

    if not user_id:
        user_id = request.args.get("current_user_id")

    if not user_id:
        data = request.get_json(silent=True) or {}
        user_id = data.get("current_user_id")

    if not user_id:
        return None

    if not ObjectId.is_valid(user_id):
        return None

    return users_collection.find_one({"_id": ObjectId(user_id)})


def get_role_permissions_from_db(role):
    permission_doc = permissions_collection.find_one({"role": role})

    if permission_doc:
        return permission_doc.get("permissions", {})

    return DEFAULT_ROLE_PERMISSIONS.get(role, {})


def user_has_permission(user, module_key, action):
    if not user:
        return False

    if user.get("status") == "NGUNG_HOAT_DONG":
        return False

    role = user.get("role")

    if role == ADMIN_ROLE:
        return True

    if not is_valid_permission(role, module_key, action):
        return False

    role_permissions = get_role_permissions_from_db(role)
    module_permissions = role_permissions.get(module_key, [])

    return action in module_permissions


def permission_required(module_key, action):
    """
    Decorator dùng để bảo vệ API.

    Ví dụ:

    @app.route("/api/users", methods=["GET"])
    @permission_required("users", "view")
    def api_get_users():
        ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_user = get_current_user_from_request()

            if not current_user:
                return jsonify({
                    "success": False,
                    "message": "Bạn chưa đăng nhập hoặc thiếu X-User-Id"
                }), 401

            if user_has_permission(current_user, module_key, action):
                return func(*args, **kwargs)

            return jsonify({
                "success": False,
                "message": "Bạn không có quyền thực hiện chức năng này"
            }), 403

        return wrapper

    return decorator


def seed_default_permissions():
    """
    Tạo quyền mặc định cho QUAN_LY và NHAN_VIEN nếu database chưa có.
    Gọi API này một lần sau khi tạo project.
    """

    created = []
    updated = []

    for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        existed = permissions_collection.find_one({"role": role})

        if existed:
            permissions_collection.update_one(
                {"role": role},
                {"$set": update_permission_model(permissions)}
            )
            updated.append(role)
        else:
            permission_doc = create_permission_model(role, permissions)
            permissions_collection.insert_one(permission_doc)
            created.append(role)

    return {
        "success": True,
        "message": "Khởi tạo quyền mặc định thành công",
        "data": {
            "created": created,
            "updated": updated
        }
    }, 200


def get_permission_options():
    return {
        "success": True,
        "message": "Lấy danh sách module phân quyền thành công",
        "data": {
            "modules": PERMISSION_MODULES,
            "roles": VALID_PERMISSION_ROLES,
            "admin_role": ADMIN_ROLE
        }
    }, 200


def get_permissions():
    docs = permissions_collection.find({
        "role": {
            "$in": VALID_PERMISSION_ROLES
        }
    })

    data = [permission_serializer(doc) for doc in docs]

    existed_roles = [item["role"] for item in data]

    for role in VALID_PERMISSION_ROLES:
        if role not in existed_roles:
            data.append({
                "id": None,
                "role": role,
                "permissions": DEFAULT_ROLE_PERMISSIONS.get(role, {}),
                "created_at": None,
                "updated_at": None,
            })

    return {
        "success": True,
        "message": "Lấy danh sách phân quyền thành công",
        "data": data
    }, 200


def get_permission_by_role(role):
    if role == ADMIN_ROLE:
        return {
            "success": True,
            "message": "ADMIN có toàn quyền hệ thống",
            "data": {
                "role": ADMIN_ROLE,
                "permissions": "ALL"
            }
        }, 200

    if role not in VALID_PERMISSION_ROLES:
        return {
            "success": False,
            "message": "Role không hợp lệ"
        }, 400

    permission_doc = permissions_collection.find_one({"role": role})

    if permission_doc:
        data = permission_serializer(permission_doc)
    else:
        data = {
            "id": None,
            "role": role,
            "permissions": DEFAULT_ROLE_PERMISSIONS.get(role, {}),
            "created_at": None,
            "updated_at": None,
        }

    return {
        "success": True,
        "message": "Lấy phân quyền theo role thành công",
        "data": data
    }, 200


def update_permission_by_role(role, data):
    if data is None:
        data = {}

    if role == ADMIN_ROLE:
        return {
            "success": False,
            "message": "Không cần cập nhật quyền cho ADMIN vì ADMIN luôn có toàn quyền"
        }, 400

    if role not in VALID_PERMISSION_ROLES:
        return {
            "success": False,
            "message": "Role không hợp lệ"
        }, 400

    permissions = data.get("permissions")

    if permissions is None:
        return {
            "success": False,
            "message": "Thiếu dữ liệu permissions"
        }, 400

    clean_permissions = normalize_permissions(permissions)

    existed = permissions_collection.find_one({"role": role})

    if existed:
        permissions_collection.update_one(
            {"role": role},
            {"$set": update_permission_model(clean_permissions)}
        )
    else:
        permission_doc = create_permission_model(role, clean_permissions)
        permissions_collection.insert_one(permission_doc)

    updated_doc = permissions_collection.find_one({"role": role})

    return {
        "success": True,
        "message": "Cập nhật phân quyền thành công",
        "data": permission_serializer(updated_doc)
    }, 200


def check_permission(data):
    if data is None:
        data = {}

    user_id = data.get("user_id")
    module_key = data.get("module")
    action = data.get("action")

    if not user_id:
        return {
            "success": False,
            "message": "Thiếu user_id"
        }, 400

    if not module_key:
        return {
            "success": False,
            "message": "Thiếu module"
        }, 400

    if not action:
        return {
            "success": False,
            "message": "Thiếu action"
        }, 400

    if not ObjectId.is_valid(user_id):
        return {
            "success": False,
            "message": "user_id không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy user"
        }, 404

    allowed = user_has_permission(user, module_key, action)

    return {
        "success": True,
        "message": "Kiểm tra quyền thành công",
        "data": {
            "allowed": allowed,
            "role": user.get("role"),
            "module": module_key,
            "action": action
        }
    }, 200


def get_my_permissions():
    current_user = get_current_user_from_request()

    if not current_user:
        return {
            "success": False,
            "message": "Bạn chưa đăng nhập hoặc thiếu X-User-Id"
        }, 401

    role = current_user.get("role")

    if role == ADMIN_ROLE:
        return {
            "success": True,
            "message": "Lấy quyền hiện tại thành công",
            "data": {
                "role": role,
                "permissions": "ALL"
            }
        }, 200

    permissions = get_role_permissions_from_db(role)

    return {
        "success": True,
        "message": "Lấy quyền hiện tại thành công",
        "data": {
            "role": role,
            "permissions": permissions
        }
    }, 200