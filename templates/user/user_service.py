from bson import ObjectId
from pymongo import DESCENDING
from werkzeug.security import generate_password_hash, check_password_hash

from mongo import users_collection, permissions_collection

from templates.user.user_model import (
    user_serializer,
    create_user_model,
    update_user_model,
    VALID_ROLES,
    VALID_STATUS,
    is_valid_object_id,
    now_vietnam,
)

from templates.permission.permission_model import (
    ADMIN_ROLE,
    PERMISSION_MODULES,
    DEFAULT_ROLE_PERMISSIONS,
)


DENIED_ACTION_MESSAGE = "Bạn không có quyền thực hiện hành động này."
MIN_CREATE_PASSWORD_LENGTH = 6
MIN_UPDATE_PASSWORD_LENGTH = 4


def normalize_role_code(role):
    role = str(role or "").strip().upper()

    mapping = {
        "ADMIN": "ADMIN",
        "QUẢN LÝ": "QUAN_LY",
        "QUAN_LY": "QUAN_LY",
        "MANAGER": "QUAN_LY",
        "NHÂN VIÊN": "NHAN_VIEN",
        "NHAN_VIEN": "NHAN_VIEN",
        "USER": "NHAN_VIEN",
        "STAFF": "NHAN_VIEN",
    }

    return mapping.get(role, role)


def user_identity_values(user):
    user = user or {}

    values = [
        user.get("_id"),
        user.get("id"),
        user.get("user_id"),
        user.get("employee_code"),
        user.get("email"),
    ]

    return {
        str(value).strip().lower()
        for value in values
        if str(value or "").strip()
    }


def is_same_user(current_user, target_user):
    # NOTE: Cho QUAN_LY thao tác với chính tài khoản QUAN_LY của mình.
    return bool(user_identity_values(current_user) & user_identity_values(target_user))


def can_manage_user_target(current_user, target_user):
    # NOTE: ADMIN thao tác tất cả.
    # QUAN_LY chỉ thao tác NHAN_VIEN hoặc chính tài khoản QUAN_LY của mình.
    if not current_user or not target_user:
        return False

    current_role = normalize_role_code(current_user.get("role"))
    target_role = normalize_role_code(target_user.get("role"))

    if current_role == "ADMIN":
        return True

    if current_role == "QUAN_LY":
        if target_role == "NHAN_VIEN":
            return True

        if target_role == "QUAN_LY" and is_same_user(current_user, target_user):
            return True

    return False


def denied_response():
    return {
        "success": False,
        "message": DENIED_ACTION_MESSAGE,
    }, 403


def get_role_permissions_for_frontend(role):
    if role == ADMIN_ROLE:
        return "ALL"

    permission_doc = permissions_collection.find_one({"role": role})

    if permission_doc:
        return permission_doc.get("permissions", {})

    return DEFAULT_ROLE_PERMISSIONS.get(role, {})


def get_module_action_map():
    module_action_map = {}

    for module in PERMISSION_MODULES:
        if not isinstance(module, dict):
            continue

        module_key = (
            module.get("key")
            or module.get("module")
            or module.get("value")
            or module.get("name")
        )

        if not module_key:
            continue

        actions = module.get("actions", [])
        action_keys = []

        for action in actions:
            if isinstance(action, dict):
                action_key = (
                    action.get("key")
                    or action.get("action")
                    or action.get("value")
                    or action.get("name")
                )

                if action_key:
                    action_keys.append(action_key)

            elif isinstance(action, str):
                action_keys.append(action)

        module_action_map[module_key] = action_keys

    return module_action_map


def build_can_object(role, permissions):
    can = {}

    if role == ADMIN_ROLE or permissions == "ALL":
        module_action_map = get_module_action_map()

        for module_key, actions in module_action_map.items():
            can[module_key] = {}

            for action in actions:
                can[module_key][action] = True

        return can

    if isinstance(permissions, dict):
        for module_key, actions in permissions.items():
            can[module_key] = {}

            if not isinstance(actions, list):
                continue

            for action in actions:
                can[module_key][action] = True

    # NOTE: QUAN_LY được mở nút users:view/update ở frontend.
    # Việc được sửa đúng tài khoản nào vẫn kiểm tra ở can_manage_user_target().
    if role == "QUAN_LY":
        can.setdefault("users", {})
        can["users"]["view"] = True
        can["users"]["update"] = True

    return can


def user_serializer_with_permissions(user):
    data = user_serializer(user)

    role = user.get("role")
    permissions = get_role_permissions_for_frontend(role)

    data["is_admin"] = role == ADMIN_ROLE
    data["permissions"] = permissions
    data["can"] = build_can_object(role, permissions)

    return data


def create_user(data):
    if data is None:
        data = {}

    required_fields = ["employee_code", "full_name", "email", "role", "password"]

    for field in required_fields:
        if not data.get(field):
            return {
                "success": False,
                "message": f"Thiếu trường bắt buộc: {field}"
            }, 400

    password = str(data.get("password") or "").strip()

    if len(password) < MIN_CREATE_PASSWORD_LENGTH:
        return {
            "success": False,
            "message": f"Mật khẩu phải có ít nhất {MIN_CREATE_PASSWORD_LENGTH} ký tự"
        }, 400

    data["password"] = password

    if data.get("role") not in VALID_ROLES:
        return {
            "success": False,
            "message": "Role không hợp lệ"
        }, 400

    if data.get("status", "HOAT_DONG") not in VALID_STATUS:
        return {
            "success": False,
            "message": "Trạng thái không hợp lệ"
        }, 400

    existed_user = users_collection.find_one({
        "$or": [
            {"employee_code": data.get("employee_code")},
            {"email": data.get("email")}
        ]
    })

    if existed_user:
        return {
            "success": False,
            "message": "Mã nhân viên hoặc email đã tồn tại"
        }, 409

    user = create_user_model(data)
    result = users_collection.insert_one(user)
    created_user = users_collection.find_one({"_id": result.inserted_id})

    return {
        "success": True,
        "message": "Tạo user thành công",
        "data": user_serializer(created_user)
    }, 201


def get_users(args):
    try:
        page = int(args.get("page", 1))
    except Exception:
        page = 1

    try:
        limit = int(args.get("limit", 10))
    except Exception:
        limit = 10

    if page < 1:
        page = 1

    if limit < 1:
        limit = 10

    skip = (page - 1) * limit

    keyword = args.get("keyword")
    role = args.get("role")
    status = args.get("status")
    department = args.get("department")
    floor = args.get("floor")

    query = {}

    if keyword:
        query["$or"] = [
            {"employee_code": {"$regex": keyword, "$options": "i"}},
            {"full_name": {"$regex": keyword, "$options": "i"}},
            {"email": {"$regex": keyword, "$options": "i"}},
            {"phone": {"$regex": keyword, "$options": "i"}},
            {"department": {"$regex": keyword, "$options": "i"}},
            {"floor": {"$regex": keyword, "$options": "i"}},
            {"role": {"$regex": keyword, "$options": "i"}},
        ]

    if role:
        query["role"] = role

    if status:
        query["status"] = status

    if department:
        query["department"] = {"$regex": department, "$options": "i"}

    if floor:
        query["floor"] = {"$regex": floor, "$options": "i"}

    total = users_collection.count_documents(query)

    users = (
        users_collection
        .find(query)
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )

    data = [user_serializer(user) for user in users]
    total_pages = (total + limit - 1) // limit if total > 0 else 1

    return {
        "success": True,
        "message": "Lấy danh sách user thành công",
        "data": data,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }
    }, 200


def get_user_by_id(id):
    if not is_valid_object_id(id):
        return {
            "success": False,
            "message": "ID không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy user"
        }, 404

    return {
        "success": True,
        "message": "Lấy chi tiết user thành công",
        "data": user_serializer(user)
    }, 200


def update_user(id, data, current_user=None):
    if data is None:
        data = {}

    if not is_valid_object_id(id):
        return {
            "success": False,
            "message": "ID không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy user"
        }, 404

    # NOTE: Chặn direct API.
    # QUAN_LY chỉ được update NHAN_VIEN hoặc chính tài khoản QUAN_LY của mình.
    if current_user is not None and not can_manage_user_target(current_user, user):
        return denied_response()

    if "role" in data and data.get("role") not in VALID_ROLES:
        return {
            "success": False,
            "message": "Role không hợp lệ"
        }, 400

    if "status" in data and data.get("status") not in VALID_STATUS:
        return {
            "success": False,
            "message": "Trạng thái không hợp lệ"
        }, 400

    if "employee_code" in data or "email" in data:
        duplicate_query = {
            "_id": {"$ne": ObjectId(id)},
            "$or": []
        }

        if data.get("employee_code"):
            duplicate_query["$or"].append({
                "employee_code": data.get("employee_code")
            })

        if data.get("email"):
            duplicate_query["$or"].append({
                "email": data.get("email")
            })

        if duplicate_query["$or"]:
            existed_user = users_collection.find_one(duplicate_query)

            if existed_user:
                return {
                    "success": False,
                    "message": "Mã nhân viên hoặc email đã tồn tại"
                }, 409

    update_data = update_user_model(data)

    # NOTE: Quản lý/Admin được đổi mật khẩu nhân viên ở màn chỉnh sửa.
    # Để trống password thì không đổi mật khẩu.
    if "password" in data:
        password = str(data.get("password") or "").strip()

        if password:
            if len(password) < MIN_UPDATE_PASSWORD_LENGTH:
                return {
                    "success": False,
                    "message": f"Mật khẩu mới phải có ít nhất {MIN_UPDATE_PASSWORD_LENGTH} ký tự"
                }, 400

            update_data["password_hash"] = generate_password_hash(password)

    if not update_data:
        return {
            "success": False,
            "message": "Không có dữ liệu để cập nhật"
        }, 400

    users_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": update_data}
    )

    updated_user = users_collection.find_one({"_id": ObjectId(id)})

    return {
        "success": True,
        "message": "Cập nhật user thành công",
        "data": user_serializer(updated_user)
    }, 200


def delete_user(id, current_user=None):
    if not is_valid_object_id(id):
        return {
            "success": False,
            "message": "ID không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy user"
        }, 404

    # NOTE: Bảo vệ API delete/ngưng hoạt động trực tiếp.
    if current_user is not None and not can_manage_user_target(current_user, user):
        return denied_response()

    users_collection.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {
                "status": "NGUNG_HOAT_DONG",
                "updated_at": now_vietnam()
            }
        }
    )

    updated_user = users_collection.find_one({"_id": ObjectId(id)})

    return {
        "success": True,
        "message": "Nhân viên đã được chuyển sang trạng thái đã nghỉ",
        "data": user_serializer(updated_user)
    }, 200


def login_user(data):
    if data is None:
        data = {}

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return {
            "success": False,
            "message": "Vui lòng nhập email và mật khẩu"
        }, 400

    user = users_collection.find_one({"email": email})

    if not user:
        return {
            "success": False,
            "message": "Email hoặc mật khẩu không đúng"
        }, 401

    password_hash = user.get("password_hash")

    if not password_hash:
        return {
            "success": False,
            "message": "Tài khoản chưa có mật khẩu"
        }, 401

    if not check_password_hash(password_hash, password):
        return {
            "success": False,
            "message": "Email hoặc mật khẩu không đúng"
        }, 401

    if user.get("status") == "NGUNG_HOAT_DONG":
        return {
            "success": False,
            "message": "Tài khoản đã ngưng hoạt động"
        }, 403

    return {
        "success": True,
        "message": "Đăng nhập thành công",
        "data": user_serializer_with_permissions(user)
    }, 200


def aggregate_counts(field_name):
    pipeline = [
        {
            "$match": {
                field_name: {
                    "$exists": True,
                    "$nin": [None, ""]
                }
            }
        },
        {
            "$group": {
                "_id": f"${field_name}",
                "count": {"$sum": 1}
            }
        },
        {
            "$sort": {
                "_id": 1
            }
        }
    ]

    result = users_collection.aggregate(pipeline)

    return {
        str(item["_id"]): item["count"]
        for item in result
    }


def get_users_stats():
    total = users_collection.count_documents({})

    role_counts = aggregate_counts("role")
    status_counts = aggregate_counts("status")
    dept_counts = aggregate_counts("department")
    floor_counts = aggregate_counts("floor")

    stats = {
        "total": total,
        "admin_count": role_counts.get("ADMIN", 0),
        "manager_count": role_counts.get("QUAN_LY", 0),
        "staff_count": role_counts.get("NHAN_VIEN", 0)
    }

    return {
        "success": True,
        "message": "Lấy thống kê user thành công",
        "data": {
            "stats": stats,
            "role_counts": role_counts,
            "status_counts": status_counts,
            "dept_counts": dept_counts,
            "floor_counts": floor_counts,
            "departments": sorted(dept_counts.keys()),
            "floors": sorted(floor_counts.keys()),
            "roles": VALID_ROLES,
            "user_status": VALID_STATUS
        }
    }, 200


def get_users_by_roles(roles):
    if not isinstance(roles, list):
        roles = [roles]

    users = users_collection.find({
        "role": {"$in": roles},
        "status": {"$ne": "NGUNG_HOAT_DONG"}
    })

    return [user_serializer(user) for user in users]


def get_admin_and_manager_users():
    return get_users_by_roles(["ADMIN", "QUAN_LY"])


def get_admin_users():
    return get_users_by_roles(["ADMIN"])


def get_manager_users():
    return get_users_by_roles(["QUAN_LY"])