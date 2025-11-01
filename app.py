import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)

# --- MongoDB 連線 ---
# 從 .env 讀取你的連線字串
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)

# 選擇你的 database 和 collection
# 你可以隨意命名，MongoDB 會在第一次使用時自動建立
db = client['flea_market']       # 資料庫名稱: flea_market
products_collection = db['products']  # 集合名稱 (Table): products
# ---------------------


@app.route('/')
def index():
    """
    Renders the homepage.
    (我們稍後會在這裡加入讀取資料庫的程式碼)
    """
    # 測試連線 (可選)
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
        
    return render_template('index.html')

# (我們稍後會在這裡加入 'add_product', 'edit_product' 等路由)


if __name__ == '__main__':
    app.run(debug=True)