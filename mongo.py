from pymongo import MongoClient

# MongoDB Atlas connection
MONGO_URI = "mongodb+srv://Minh:123@cluster0.vknafoi.mongodb.net/asset_management?retryWrites=true&w=majority"
DB_NAME = "asset_management"

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collection assets
assets_collection = db["assets"]
assign_collection = db["assign"]