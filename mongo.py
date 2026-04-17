from pymongo import MongoClient
from datetime import datetime

client = MongoClient('mongodb://localhost:27017/')
db = client['it_assets_db']
assets = db['assets']

# Thêm 1 document mock để tạo database + collection
assets.insert_one({
    "name": "Laptop Dell XPS",
    "type": "Laptop",
    "serial_number": "SN123456",
    "status": "available",
    "assigned_to": None,
    "created_at": datetime.utcnow()
})

print("Database + collection created with 1 mock record")