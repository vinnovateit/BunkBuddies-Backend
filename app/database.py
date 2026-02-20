"""MongoDB Database Connection"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import settings

client: AsyncIOMotorClient = None
database: AsyncIOMotorDatabase = None


async def connect_to_mongo():
    """Connect to MongoDB"""
    global client, database
    client = AsyncIOMotorClient(settings.mongodb_url)
    database = client[settings.database_name]
    await database["students"].create_index("regNo", unique=True)
    await database["students"].create_index("firebaseUID", unique=True)
    await database["groups"].create_index("groupCode", unique=True, sparse=True)
    await database["group_requests"].create_index(
        [("groupId", 1), ("studentRegNo", 1)],
        unique=True,
    )
    print(f"Connected to MongoDB: {settings.database_name}")


async def close_mongo_connection():
    """Close MongoDB connection"""
    global client
    if client:
        client.close()
        print("Closed MongoDB connection")


def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    return database
