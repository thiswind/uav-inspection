from motor.motor_asyncio import AsyncIOMotorClient
from pestapp.core.config import settings

class MongoDBManager:
    client: AsyncIOMotorClient = None
    db = None

db_manager = MongoDBManager()

async def connect_to_mongo():
    """在 FastAPI 启动时连接 MongoDB"""
    print(f"Connecting to MongoDB at {settings.MONGO_URI}...")
    # 为了演示如果没起 MongoDB 不至于卡死，这里只是初始化 client 对象
    db_manager.client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
    db_manager.db = db_manager.client[settings.DATABASE_NAME]
    
async def close_mongo_connection():
    """在 FastAPI 关闭时断开连接"""
    if db_manager.client:
        db_manager.client.close()
        print("MongoDB connection closed.")