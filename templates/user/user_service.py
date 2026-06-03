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


# Lấy quyền của role từ database.
# Nếu database chưa có thì lấy quyền mặc định trong DEFAULT_ROLE_PERMISSIONS.
def get_role_permissions_for_frontend(role):
    if role == ADMIN_ROLE:
        return "ALL"

    permission_doc = permissions_collection.find_one({"role": role})

    if permission_doc:
        return permission_doc.get("permissions", {})

    return DEFAULT_ROLE_PERMISSIONS.get(role, {})


# Lấy danh sách action từ PERMISSION_MODULES.
# Viết kiểu mềm để tránh lỗi nếu permission_model đang khai báo module hơi khác format.
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


# Tạo object can để frontend dùng ẩn/hiện nút.
# Ví dụ:
# can.users.view
# can.users.create
# can.users.update
# can.users.delete
def build_can_object(role, permissions):
    can = {}

    if role == ADMIN_ROLE or permissions == "ALL":
        module_action_map = get_module_action_map()

        for module_key, actions in module_action_map.items():
            can[module_key] = {}

            for action in actions:
                can[module_key][action] = True

        return can

    if not isinstance(permissions, dict):
        return can

    for module_key, actions in permissions.items():
        can[module_key] = {}

        if not isinstance(actions, list):
            continue

        for action in actions:
            can[module_key][action] = True

    return can


# Gắn quyền vào user trả về frontend sau login.
def user_serializer_with_permissions(user):
    data = user_serializer(user)

    role = user.get("role")
    permissions = get_role_permissions_for_frontend(role)

    data["is_admin"] = role == ADMIN_ROLE
    data["permissions"] = permissions
    data["can"] = build_can_object(role, permissions)

    return data


# Tạo user mới
# Kiểm tra dữ liệu bắt buộc, role, trạng thái và trùng mã nhân viên/email trước khi lưu
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

    if len(data.get("password")) < 6:
        return {
            "success": False,
            "message": "Mật khẩu phải có ít nhất 6 ký tự"
        }, 400

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


# Lấy danh sách user
# Có hỗ trợ phân trang, tìm kiếm và lọc theo role, trạng thái, phòng ban, tầng
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


# Lấy chi tiết một user theo id
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


# Cập nhật thông tin user theo id
# Có kiểm tra id, user tồn tại, role, trạng thái và trùng mã nhân viên/email
def update_user(id, data):
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

    if "password" in data and data.get("password"):
        if len(data.get("password")) < 6:
            return {
                "success": False,
                "message": "Mật khẩu phải có ít nhất 6 ký tự"
            }, 400

        update_data["password_hash"] = generate_password_hash(data.get("password"))

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


# Xóa user theo id
# Trong nghiệp vụ hiện tại: xóa nhân sự = chuyển sang trạng thái đã nghỉ
# Không xóa record khỏi MongoDB để trang thống kê vẫn đếm được nhân viên đã nghỉ
def delete_user(id):
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


# Đăng nhập user
# Trả thêm permissions và can để frontend ẩn/hiện nút
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


# Đếm số lượng user theo một field bất kỳ
# Ví dụ: đếm theo role, status, department hoặc floor
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


# Lấy thống kê tổng quan user
# Bao gồm tổng user, số lượng theo role, trạng thái, phòng ban và tầng
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


# Lấy danh sách user theo một hoặc nhiều role
# Chỉ lấy user còn hoạt động để dùng cho notification hoặc phân quyền
def get_users_by_roles(roles):
    if not isinstance(roles, list):
        roles = [roles]

    users = users_collection.find({
        "role": {"$in": roles},
        "status": {"$ne": "NGUNG_HOAT_DONG"}
    })

    return [user_serializer(user) for user in users]


# Lấy danh sách ADMIN và QUAN_LY còn hoạt động
def get_admin_and_manager_users():
    return get_users_by_roles(["ADMIN", "QUAN_LY"])


# Lấy danh sách ADMIN còn hoạt động
def get_admin_users():
    return get_users_by_roles(["ADMIN"])


# Lấy danh sách QUAN_LY còn hoạt động
def get_manager_users():
    return get_users_by_roles(["QUAN_LY"])