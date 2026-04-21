from flask import Flask, jsonify
from flask_cors import CORS
from templates.asset.asset_app import register_assets_api_routes

app = Flask(__name__)
CORS(app)

register_assets_api_routes(app)

@app.route("/")
def home():
    return jsonify({
        "message": "Backend API is running",
        "assets_api": "/api/assets"
    })

if __name__ == "__main__":
    app.run(debug=True, port=5001)