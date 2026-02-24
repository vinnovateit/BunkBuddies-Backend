"""FastAPI Application Entry Point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routers import auth, group, group_requests, student, users


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    # Startup
    await connect_to_mongo()

    try:
        yield
    finally:
        # Shutdown
        await close_mongo_connection()


# Create FastAPI app
app = FastAPI(
    title="BunkBuddies API",
    description="FastAPI backend with MongoDB and Google authentication",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(student.router)
app.include_router(group.router)
app.include_router(group_requests.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to BunkBuddies API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
