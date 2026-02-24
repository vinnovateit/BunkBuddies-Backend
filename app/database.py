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

    # Ensure uniqueness only for issued (string) invite codes, not null/missing values.
    group_indexes = await database["groups"].index_information()
    group_code_index = group_indexes.get("groupCode_1")
    expected_partial = {"groupCode": {"$type": "string"}}
    needs_rebuild = False
    if group_code_index:
        has_unique = bool(group_code_index.get("unique"))
        partial_filter = group_code_index.get("partialFilterExpression")
        if not has_unique or partial_filter != expected_partial:
            needs_rebuild = True

    if needs_rebuild:
        await database["groups"].drop_index("groupCode_1")

    await database["groups"].create_index(
        "groupCode",
        unique=True,
        partialFilterExpression=expected_partial,
    )
    await database["group_requests"].create_index(
        [("groupId", 1), ("studentRegNo", 1)],
        unique=True,
    )
    await database["group_requests"].create_index([("status", 1), ("adminDigestSentAt", 1), ("createdAt", -1)])
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
