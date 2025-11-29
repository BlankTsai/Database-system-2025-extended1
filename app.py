import os
from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
from bson.objectid import ObjectId

# 載入 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # [NEW] 用於 flash 訊息 (Session)

# --- MongoDB 連線 (保持原本較嚴謹的連線檢查版本) ---
mongo_uri = os.getenv('MONGO_URI')
client = None 

try:
    # 告訴 MongoClient 等 60 秒 (60000ms)，並在啟動時測試連線
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=60000 
    )
    client.admin.command('ping')
    print("MongoDB connected successfully.")
    
except Exception as e:
    print(f"CRITICAL: Error connecting to MongoDB: {e}")
    # 如果連線失敗，client 會保持為 None

# 檢查 client 是否成功連線
if client:
    db = client['flea_market']
    products_collection = db['products']
else:
    print("CRITICAL: MongoDB client is None. Database will not work.")
    db = None
    products_collection = None
# ---------------------

# [NEW] 輔助函式：檢查資料庫連線
def check_db():
    if products_collection is None:
        return False
    return True

# --- 1. 首頁 + 進階搜尋 (整合新舊功能) ---
@app.route('/')
def index():
    """
    Renders the homepage. Supports keyword search via ?q=...
    """
    if not check_db(): return "Database Error", 500

    # 取得搜尋關鍵字
    query = request.args.get('q')
    
    if query:
        # [作業重點 1] db.collection.find (帶查詢條件)
        # 使用 $regex 進行模糊搜尋 (不分大小寫)
        filter_criteria = {"name": {"$regex": query, "$options": "i"}}
        products = list(products_collection.find(filter_criteria).sort("_id", -1))
    else:
        # 如果沒有搜尋，顯示全部 (原本的邏輯)
        products = list(products_collection.find().sort("_id", -1))
    
    # 傳遞 search_query 給 template 以便在搜尋框保留文字
    return render_template('index.html', products=products, search_query=query)


# --- 2. 數據分析 Dashboard (新功能) ---
@app.route('/dashboard')
def dashboard():
    if not check_db(): return "Database Error", 500

    # [作業重點 2] db.collection.aggregate
    pipeline = [
        {
            "$group": {
                "_id": None, # 不分組，統計全部
                "total_products": {"$sum": 1},          # 總數量
                "total_value": {"$sum": "$price"},      # 總價值
                "avg_price": {"$avg": "$price"},        # 平均價格
                "max_price": {"$max": "$price"}         # 最高價
            }
        }
    ]
    
    stats = list(products_collection.aggregate(pipeline))
    
    # 如果資料庫是空的，給預設值
    data = stats[0] if stats else {
        "total_products": 0, "total_value": 0, "avg_price": 0, "max_price": 0
    }
    
    return render_template('dashboard.html', stats=data)


# --- 3. 批次更新 (新功能) ---
@app.route('/bulk_update', methods=['POST'])
def bulk_update():
    if not check_db(): return "Database Error", 500

    # 範例功能：將所有價格 > 1000 的商品打 9 折
    threshold = 1000
    discount = 0.9
    
    # [作業重點 3] db.collection.updateMany
    result = products_collection.update_many(
        {"price": {"$gt": threshold}},      # 條件：價格大於 1000
        {"$mul": {"price": discount}}       # 動作：價格 * 0.9
    )
    
    msg = f"已成功更新 {result.modified_count} 筆商品 (高於 ${threshold} 打 9 折)"
    print(msg) 
    # 若要在頁面上顯示提示，需在 dashboard.html 實作 get_flashed_messages()
    flash(msg)
    return redirect(url_for('dashboard'))


# --- 4. 批次刪除 (新功能) ---
@app.route('/bulk_delete', methods=['POST'])
def bulk_delete():
    if not check_db(): return "Database Error", 500

    # 範例功能：刪除所有價格 < 100 的商品 (清倉)
    threshold = 100
    
    # [作業重點 4] db.collection.deleteMany
    result = products_collection.delete_many(
        {"price": {"$lt": threshold}}       # 條件：價格小於 100
    )
    
    msg = f"已成功刪除 {result.deleted_count} 筆低價商品 (< ${threshold})"
    print(msg)
    flash(msg)
    return redirect(url_for('dashboard'))


# --- 以下保持原本的新增、編輯、刪除功能 ---

@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if not check_db(): return "Database Error", 500
    
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


@app.route('/delete/<product_id>', methods=['POST'])
def delete_product(product_id):
    if not check_db(): return "Database Error", 500
    try:
        obj_id = ObjectId(product_id)
        products_collection.delete_one({"_id": obj_id})
    except Exception as e:
        print(f"Error deleting product: {e}")
    return redirect(url_for('index'))


@app.route('/edit/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if not check_db(): return "Database Error", 500
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