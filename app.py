import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
from bson.objectid import ObjectId  # [NEW] 匯入 ObjectId，用於刪除與更新商品

# 載入 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)

# --- MongoDB 連線 ---
mongo_uri = os.getenv('MONGO_URI')
client = None # 先設為 None

try:
    # [NEW] 告訴 MongoClient 等 60 秒 (60000ms)，而不是預設的 30 秒
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=60000  # 60 秒
    )
    # [NEW] 在啟動時就測試一次連線
    client.admin.command('ping')
    print("MongoDB connected successfully.")
    
except Exception as e:
    print(f"CRITICAL: Error connecting to MongoDB: {e}")
    # 如果連線失敗，client 會保持為 None

# [NEW] 檢查 client 是否成功連線
if client:
    db = client['flea_market']
    products_collection = db['products']
else:
    # 如果連線失敗，將 db 和 collection 設為 None
    print("CRITICAL: MongoDB client is None. Database will not work.")
    db = None
    products_collection = None
# ---------------------

@app.route('/')
def index():
    """
    Renders the homepage and displays all products.
    """
    # 從資料庫讀取所有商品 (最新的排前面)
    all_products = list(products_collection.find().sort("_id", -1))
    return render_template('index.html', products=all_products)


# --- 新增商品 ---
@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'single':
            # 單筆新增
            name = request.form.get('name')
            description = request.form.get('description')
            price = request.form.get('price')

            product = {
                "name": name,
                "description": description,
                "price": float(price),
                "created_at": datetime.utcnow()
            }

            products_collection.insert_one(product)

        elif form_type == 'batch':
            # 多筆新增
            batch_names = request.form.getlist('batch_name')
            batch_prices = request.form.getlist('batch_price')

            products_to_insert = []

            for name, price in zip(batch_names, batch_prices):
                if name and price:
                    product = {
                        "name": name,
                        "description": "多筆上架商品",
                        "price": float(price),
                        "created_at": datetime.utcnow()
                    }
                    products_to_insert.append(product)

            if products_to_insert:
                products_collection.insert_many(products_to_insert)

        return redirect(url_for('index'))

    return render_template('add_product.html')


# --- [NEW] 刪除商品 ---
@app.route('/delete/<product_id>', methods=['POST'])
def delete_product(product_id):
    try:
        obj_id = ObjectId(product_id)
        products_collection.delete_one({"_id": obj_id})
    except Exception as e:
        print(f"Error deleting product: {e}")
    return redirect(url_for('index'))


# --- [NEW] 編輯商品 (GET 顯示 / POST 更新) ---
@app.route('/edit/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    try:
        obj_id = ObjectId(product_id)
    except Exception as e:
        print(f"Invalid ObjectId: {e}")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # 處理更新邏輯
        updated_name = request.form.get('name')
        updated_description = request.form.get('description')
        updated_price = float(request.form.get('price'))

        products_collection.update_one(
            {"_id": obj_id},
            {"$set": {
                "name": updated_name,
                "description": updated_description,
                "price": updated_price
            }}
        )
        return redirect(url_for('index'))
    else:
        # 顯示編輯頁面
        product = products_collection.find_one({"_id": obj_id})
        if product:
            return render_template('edit_product.html', product=product)
        else:
            return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
