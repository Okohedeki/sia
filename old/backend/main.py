"""
Sia Backend - Work Unit Coordination Server for Claude Code.

This is the lockd daemon that provides:
- Work unit registration and claiming
- FIFO queue management for contested resources
- Global visibility for all agents
- TTL-based automatic cleanup

Run with: uvicorn backend.main:app --host 127.0.0.1 --port 7432 --reload
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .registry import WorkUnitRegistry
from .routes import agents as agents_routes
from .routes import work_units as work_units_routes


# Global registry instance
registry = WorkUnitRegistry(default_ttl_seconds=300)

# Background cleanup task
cleanup_task: asyncio.Task | None = None


async def periodic_cleanup():
    """Background task to clean up expired work units and agents."""
    while True:
        try:
            await asyncio.sleep(30)  # Run every 30 seconds
            released = registry.cleanup_expired()
            if released:
                print(f"[Cleanup] Released expired work units: {released}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Cleanup] Error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global cleanup_task

    # Startup
    print("=" * 60)
    print("Sia Backend - Work Unit Coordination Server")
    print("=" * 60)
    print(f"Registry initialized with TTL: {registry._default_ttl}s")

    # Start background cleanup
    cleanup_task = asyncio.create_task(periodic_cleanup())
    print("Background cleanup task started")

    yield

    # Shutdown
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    print("Sia Backend shutting down")


# Create FastAPI app
app = FastAPI(
    title="Sia Backend",
    description="Work Unit Coordination Server for Claude Code multi-agent workflows",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject registry into route modules
agents_routes.set_registry(registry)
work_units_routes.set_registry(registry)

# Include routers
app.include_router(agents_routes.router)
app.include_router(work_units_routes.router)


@app.get("/")
def root():
    """Health check and basic info."""
    return {
        "name": "Sia Backend",
        "version": "0.1.0",
        "status": "running",
        "description": "Work Unit Coordination Server for Claude Code",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    state = registry.get_state()
    return {
        "status": "healthy",
        "agents_count": len(state["agents"]),
        "work_units_count": len(state["work_units"]),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=7432,
        reload=True,
    )
