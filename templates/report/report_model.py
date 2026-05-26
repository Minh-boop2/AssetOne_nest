# Model report: làm việc trực tiếp với collection reports và xử lý file upload
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson import ObjectId
from werkzeug.utils import secure_filename

from mongo import reports_collection


# Lấy đường dẫn thư mục hiện tại của file report_model.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Tạo đường dẫn tới thư mục uploads trong folder report
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# Tạo thư mục uploads nếu chưa tồn tại
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Múi giờ Việt Nam UTC+7
VN_TZ = timezone(timedelta(hours=7))


# Các loại báo cáo được phép chọn
REPORT_TYPES = [
    "Báo hỏng",
    "Cần cấp mới",
    "Khác",
]

# Các trạng thái báo cáo trong hệ thống
REPORT_STATUSES = [
    "Chờ xử lý",
    "Hoàn thành",
    "Đã hủy",
]

# Tên role hiển thị cho người gửi báo cáo
REPORTER_ROLES = [
    "Admin",
    "Manager",
    "Staff",
]

# Các định dạng file được phép upload
ALLOWED_FILE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "zip",
    "rar",
}


# Lấy thời gian hiện tại theo múi giờ Việt Nam
def current_vietnam_datetime():
    return datetime.now(VN_TZ)


# Lấy thời gian Việt Nam dạng chuỗi để hiển thị
def current_vietnam_time():
    return current_vietnam_datetime().strftime("%H:%M %d/%m/%Y")


# Đổi datetime sang chuỗi ngày giờ Việt Nam
def format_datetime_vietnam(value):
    if not value:
        return ""

    if isinstance(value, str):
        return value

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M")


# Kiểm tra một giá trị có phải ObjectId hợp lệ hay không
def is_valid_object_id(value):
    return ObjectId.is_valid(str(value))


# Tạo query tìm báo cáo bằng ObjectId hoặc bằng report_code
def build_report_id_query(report_id):
    report_id = str(report_id)

    if ObjectId.is_valid(report_id):
        return {"_id": ObjectId(report_id)}

    return {"report_code": report_id}


# Chuẩn hóa dữ liệu báo cáo trước khi trả về frontend
def serialize_report(report):
    if not report:
        return None

    item = dict(report)

    item["id"] = str(item.get("_id", ""))
    item.pop("_id", None)

    item["created_at"] = format_datetime_vietnam(item.get("created_at"))
    item["updated_at"] = format_datetime_vietnam(item.get("updated_at"))
    item["approved_at"] = format_datetime_vietnam(item.get("approved_at"))
    item["cancelled_at"] = format_datetime_vietnam(item.get("cancelled_at"))

    item["report_code"] = item.get("report_code") or ""
    item["report_name"] = item.get("report_name") or ""
    item["report_type"] = item.get("report_type") or ""
    item["status"] = item.get("status") or "Chờ xử lý"

    item["reporter_user_id"] = item.get("reporter_user_id") or ""
    item["reporter_employee_code"] = item.get("reporter_employee_code") or ""
    item["reporter_email"] = item.get("reporter_email") or ""
    item["reporter"] = item.get("reporter") or ""
    item["reporter_role"] = item.get("reporter_role") or ""

    item["asset_id"] = item.get("asset_id") or ""
    item["asset_code"] = item.get("asset_code") or ""
    item["asset_name"] = item.get("asset_name") or "Chưa xác định"
    item["asset_type"] = item.get("asset_type") or ""
    item["asset_status"] = item.get("asset_status") or ""

    item["department"] = item.get("department") or ""
    item["location"] = item.get("location") or ""
    item["description"] = item.get("description") or ""
    item["time"] = item.get("time") or ""

    files = item.get("files", [])

    if not isinstance(files, list):
        files = []

    item["files"] = files

    return item


# Đếm số lượng báo cáo, có thể đếm theo điều kiện query
def count_reports(query=None):
    return reports_collection.count_documents(query or {})


# Tìm danh sách báo cáo, có phân trang và sắp xếp
def find_reports(query=None, skip=0, limit=10, sort_field="_id", sort_order=-1):
    return list(
        reports_collection
        .find(query or {})
        .sort(sort_field, sort_order)
        .skip(skip)
        .limit(limit)
    )


# Tìm một báo cáo theo điều kiện query
def find_report_by_query(query):
    return reports_collection.find_one(query)


# Thêm một báo cáo mới vào database
def insert_report(data):
    return reports_collection.insert_one(data)


# Cập nhật một báo cáo theo điều kiện query
def update_report_by_query(query, update_data):
    return reports_collection.update_one(
        query,
        {
            "$set": update_data
        }
    )


# Xóa một báo cáo theo điều kiện query
def delete_report_by_query(query):
    return reports_collection.delete_one(query)


# Tìm báo cáo theo mã report_code
def find_report_by_code(report_code):
    return reports_collection.find_one({
        "report_code": report_code
    })


# Tạo mã báo cáo tăng dần kiểu Report-000001
def generate_report_code():
    last_report = reports_collection.find_one(
        {
            "report_code": {
                "$regex": r"^Report-\d{6}$"
            }
        },
        sort=[("report_code", -1)]
    )

    if not last_report:
        return "Report-000001"

    last_code = last_report.get("report_code", "Report-000000")

    try:
        number = int(last_code.replace("Report-", ""))
    except Exception:
        number = 0

    next_number = number + 1

    while True:
        report_code = f"Report-{next_number:06d}"

        if not find_report_by_code(report_code):
            return report_code

        next_number += 1


# Kiểm tra file upload có đúng định dạng cho phép không
def is_allowed_file(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_FILE_EXTENSIONS


# Lưu file upload vào thư mục uploads và trả thông tin file
def save_uploaded_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    original_filename = file_storage.filename
    safe_filename = secure_filename(original_filename)

    if not safe_filename:
        raise ValueError("Tên file không hợp lệ.")

    if not is_allowed_file(safe_filename):
        raise ValueError(f"Định dạng file không được hỗ trợ: {original_filename}")

    extension = safe_filename.rsplit(".", 1)[1].lower()
    stored_filename = f"{uuid4().hex}.{extension}"
    full_path = os.path.join(UPLOAD_FOLDER, stored_filename)

    file_storage.save(full_path)

    return {
        "id": uuid4().hex,
        "original_name": original_filename,
        "stored_name": stored_filename,
        "extension": extension,
        "mime_type": file_storage.mimetype,
        "size": os.path.getsize(full_path),
        "url": f"/api/reports/files/{stored_filename}",
        "uploaded_at": current_vietnam_time(),
    }


# Xóa file đã upload khỏi thư mục uploads
def delete_uploaded_file(file_record):
    if not file_record:
        return False

    stored_name = file_record.get("stored_name")

    if not stored_name:
        return False

    full_path = os.path.join(UPLOAD_FOLDER, stored_name)

    if os.path.exists(full_path):
        os.remove(full_path)
        return True

    return False