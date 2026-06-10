# File này xử lý logic chính cho hồ sơ cá nhân:
# - Lấy thông tin người đang đăng nhập
# - Lấy avatar, trạng thái, role
# - Đếm tài sản theo role
# - Lấy 5 nhật ký hoạt động mới nhất của chính người đó
# - Cập nhật hồ sơ
# - Đổi mật khẩu

import os
import uuid

from bson import ObjectId
from pymongo import DESCENDING
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from mongo import users_collection, activities_collection, assets_collection

from templates.profile.profile_model import (
    profile_serializer,
    update_profile_model,
    is_allowed_avatar_file,
    get_avatar_file_extension,
    AVATAR_UPLOAD_SUBDIR,
    MAX_AVATAR_SIZE,
)

from templates.user.user_model import (
    is_valid_object_id,
    now_vietnam,
    format_datetime_vietnam,
)


# Các role này xem tài sản theo phạm vi toàn hệ thống
FULL_ASSET_ROLES = ["ADMIN", "QUAN_LY"]


# Ép dữ liệu về số nguyên an toàn, tránh lỗi khi dữ liệu rỗng hoặc sai kiểu
def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


# Kiểm tra user có được xem toàn bộ tài sản hệ thống hay không
def user_can_view_all_assets(user):
    return bool(user and user.get("role") in FULL_ASSET_ROLES)


# Chuẩn hóa 1 dòng nhật ký hoạt động để frontend profile hiển thị được
def serialize_profile_activity(activity):
    metadata = activity.get("metadata") or {}

    target_name = (
        activity.get("target_name")
        or metadata.get("target_name")
        or metadata.get("asset_name")
        or metadata.get("full_name")
        or metadata.get("employee_name")
        or metadata.get("name")
        or metadata.get("title")
        or activity.get("path")
        or "Không xác định"
    )

    created_at = format_datetime_vietnam(activity.get("created_at"))

    return {
        "id": str(activity.get("_id")),
        "time": created_at or "",
        "created_at": created_at or "",
        "action": activity.get("action") or "Hoạt động",
        "module": activity.get("module"),
        "method": activity.get("method"),
        "target_id": str(activity.get("target_id")) if activity.get("target_id") else None,
        "target_name": target_name,
        "asset": target_name,
    }


# Chuẩn hóa 1 tài sản để trả về trong dữ liệu profile
def serialize_profile_asset(asset):
    asset_name = (
        asset.get("asset_name")
        or asset.get("asset")
        or asset.get("asset_code")
        or "Tài sản"
    )

    return {
        "id": str(asset.get("_id")),
        "asset_code": asset.get("asset_code") or "",
        "asset_name": asset_name,
        "asset": asset_name,
        "status": asset.get("status") or "",
        "user_id": str(asset.get("user_id") or ""),
        "employee_code": asset.get("employee_code") or "",
        "receiver": asset.get("receiver") or asset.get("user") or "",
        "user": asset.get("user") or asset.get("receiver") or "",
        "department": asset.get("department") or "",
        "location": asset.get("location") or "",
    }


# Tạo query lấy tài sản theo role:
# ADMIN / QUAN_LY xem toàn bộ hệ thống, NHAN_VIEN chỉ xem tài sản của chính mình
def build_profile_asset_query(user):
    if not user:
        return {"_id": {"$exists": False}}

    if user_can_view_all_assets(user):
        return {}

    user_id = user.get("_id")
    user_id_text = str(user_id) if user_id else ""
    employee_code = (user.get("employee_code") or "").strip()
    email = (user.get("email") or "").strip()
    full_name = (user.get("full_name") or user.get("name") or "").strip()

    owner_conditions = []

    if user_id:
        owner_conditions.append({"user_id": user_id})
        owner_conditions.append({"user_id": user_id_text})

    if employee_code:
        owner_conditions.append({"employee_code": employee_code})

    if email:
        owner_conditions.append({"email": email})

    if full_name:
        owner_conditions.append({"receiver": full_name})
        owner_conditions.append({"user": full_name})

    if not owner_conditions:
        return {"_id": {"$exists": False}}

    return {"$or": owner_conditions}


# Lấy số lượng tài sản và vài tài sản gần nhất để đưa vào profile
def get_profile_assets_summary(user, limit=5):
    if not user:
        return {
            "asset_count": 0,
            "held_assets_count": 0,
            "held_assets": [],
            "asset_scope": "none",
        }

    limit = max(1, min(safe_int(limit, 5), 20))
    query = build_profile_asset_query(user)

    total = assets_collection.count_documents(query)

    assets = (
        assets_collection
        .find(query)
        .sort("_id", DESCENDING)
        .limit(limit)
    )

    return {
        "asset_count": total,
        "held_assets_count": total,
        "held_assets": [serialize_profile_asset(asset) for asset in assets],
        "asset_scope": "all_system" if user_can_view_all_assets(user) else "own",
    }


# Tạo query lấy nhật ký hoạt động của chính user hiện tại
def build_profile_activity_query(user):
    if not user:
        return {"_id": None}

    user_id = user.get("_id")
    employee_code = user.get("employee_code")
    email = user.get("email")
    full_name = user.get("full_name")

    conditions = []

    if user_id:
        conditions.append({"user_id": user_id})
        conditions.append({"user_id": str(user_id)})

    if employee_code:
        conditions.append({"employee_code": employee_code})

    if email:
        conditions.append({"email": email})

    if full_name:
        conditions.append({"full_name": full_name})

    if not conditions:
        return {"_id": None}

    return {"$or": conditions}


# Lấy tối đa 5 nhật ký hoạt động mới nhất của user hiện tại
def get_recent_activities_for_profile(user, limit=5):
    if not user:
        return []

    limit = max(1, min(safe_int(limit, 5), 20))

    activities = (
        activities_collection
        .find(build_profile_activity_query(user))
        .sort("created_at", DESCENDING)
        .limit(limit)
    )

    return [serialize_profile_activity(activity) for activity in activities]


# Gộp toàn bộ dữ liệu profile gồm thông tin user, tài sản và nhật ký hoạt động
def build_profile_response_data(user):
    data = profile_serializer(user)
    data.update(get_profile_assets_summary(user, 5))
    data["recent_activities"] = get_recent_activities_for_profile(user, 5)
    return data


# Lấy dung lượng file upload
def get_uploaded_file_size(file):
    try:
        current_position = file.stream.tell()
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(current_position)
        return size
    except Exception:
        return 0


# Tạo đường dẫn lưu avatar và đường dẫn trả về frontend
def build_avatar_save_info(root_path, user_id, original_filename):
    extension = get_avatar_file_extension(original_filename)
    safe_user_id = secure_filename(str(user_id))
    filename = f"{safe_user_id}_{uuid.uuid4().hex}.{extension}"

    upload_dir = os.path.join(root_path, "static", *AVATAR_UPLOAD_SUBDIR.split("/"))
    os.makedirs(upload_dir, exist_ok=True)

    save_path = os.path.join(upload_dir, filename)
    avatar_url = f"/static/{AVATAR_UPLOAD_SUBDIR}/{filename}".replace("\\", "/")

    return save_path, avatar_url


# Xóa avatar cũ nếu avatar đó nằm trong thư mục upload của hệ thống
def delete_old_avatar_file(root_path, avatar_url):
    if not avatar_url:
        return

    upload_prefix = f"/static/{AVATAR_UPLOAD_SUBDIR}/"

    if not str(avatar_url).startswith(upload_prefix):
        return

    try:
        relative_path = str(avatar_url).lstrip("/").replace("/", os.sep)
        file_path = os.path.abspath(os.path.join(root_path, relative_path))
        upload_dir = os.path.abspath(os.path.join(root_path, "static", *AVATAR_UPLOAD_SUBDIR.split("/")))

        if file_path.startswith(upload_dir) and os.path.exists(file_path):
            os.remove(file_path)

    except Exception:
        pass


# Lấy hồ sơ của người đang đăng nhập
def get_my_profile(user_id):
    if not user_id:
        return {
            "success": False,
            "message": "Thiếu thông tin người dùng đăng nhập"
        }, 401

    if not is_valid_object_id(user_id):
        return {
            "success": False,
            "message": "ID người dùng không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy người dùng"
        }, 404

    return {
        "success": True,
        "message": "Lấy thông tin hồ sơ thành công",
        "data": build_profile_response_data(user)
    }, 200


# Cập nhật thông tin hồ sơ của người đang đăng nhập
def update_my_profile(user_id, data):
    if data is None:
        data = {}

    if not user_id:
        return {
            "success": False,
            "message": "Thiếu thông tin người dùng đăng nhập"
        }, 401

    if not is_valid_object_id(user_id):
        return {
            "success": False,
            "message": "ID người dùng không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy người dùng"
        }, 404

    if "email" in data and data.get("email"):
        email = data.get("email").strip()

        existed_user = users_collection.find_one({
            "_id": {"$ne": ObjectId(user_id)},
            "email": email
        })

        if existed_user:
            return {
                "success": False,
                "message": "Email đã tồn tại"
            }, 409

    update_data = update_profile_model(data)

    if not update_data:
        return {
            "success": False,
            "message": "Không có dữ liệu để cập nhật"
        }, 400

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )

    updated_user = users_collection.find_one({"_id": ObjectId(user_id)})

    return {
        "success": True,
        "message": "Cập nhật hồ sơ thành công",
        "data": build_profile_response_data(updated_user)
    }, 200


# Tải lên avatar mới của người đang đăng nhập
def upload_my_avatar(user_id, file, root_path):
    if not user_id:
        return {
            "success": False,
            "message": "Thiếu thông tin người dùng đăng nhập"
        }, 401

    if not is_valid_object_id(user_id):
        return {
            "success": False,
            "message": "ID người dùng không hợp lệ"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy người dùng"
        }, 404

    if not file or not file.filename:
        return {
            "success": False,
            "message": "Vui lòng chọn ảnh đại diện"
        }, 400

    original_filename = secure_filename(file.filename)

    if not is_allowed_avatar_file(original_filename):
        return {
            "success": False,
            "message": "Ảnh đại diện chỉ hỗ trợ png, jpg, jpeg, gif hoặc webp"
        }, 400

    file_size = get_uploaded_file_size(file)

    if file_size and file_size > MAX_AVATAR_SIZE:
        return {
            "success": False,
            "message": "Ảnh đại diện không được vượt quá 3MB"
        }, 400

    save_path, avatar_url = build_avatar_save_info(root_path, user_id, original_filename)

    try:
        file.stream.seek(0)
        file.save(save_path)
    except Exception as error:
        return {
            "success": False,
            "message": "Không thể lưu ảnh đại diện",
            "error": str(error)
        }, 500

    old_avatar_url = user.get("avatar_url")

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "avatar_url": avatar_url,
                "updated_at": now_vietnam()
            }
        }
    )

    updated_user = users_collection.find_one({"_id": ObjectId(user_id)})

    delete_old_avatar_file(root_path, old_avatar_url)

    return {
        "success": True,
        "message": "Cập nhật ảnh đại diện thành công",
        "data": build_profile_response_data(updated_user)
    }, 200


# Đổi mật khẩu của người đang đăng nhập
def change_my_password(user_id, data):
    if data is None:
        data = {}

    if not user_id:
        return {
            "success": False,
            "message": "Thiếu thông tin người dùng đăng nhập"
        }, 401

    if not is_valid_object_id(user_id):
        return {
            "success": False,
            "message": "ID người dùng không hợp lệ"
        }, 400

    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return {
            "success": False,
            "message": "Vui lòng nhập mật khẩu cũ và mật khẩu mới"
        }, 400

    if len(new_password) < 6:
        return {
            "success": False,
            "message": "Mật khẩu mới phải có ít nhất 6 ký tự"
        }, 400

    user = users_collection.find_one({"_id": ObjectId(user_id)})

    if not user:
        return {
            "success": False,
            "message": "Không tìm thấy người dùng"
        }, 404

    password_hash = user.get("password_hash")

    if not password_hash or not check_password_hash(password_hash, old_password):
        return {
            "success": False,
            "message": "Mật khẩu cũ không đúng"
        }, 400

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "password_hash": generate_password_hash(new_password),
                "updated_at": now_vietnam()
            }
        }
    )

    return {
        "success": True,
        "message": "Đổi mật khẩu thành công"
    }, 200