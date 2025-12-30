"""Database engine and session management for TheWallflower."""

import logging
from pathlib import Path
from typing import Generator

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import event

from app.config import settings

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get the database URL, ensuring the directory exists.

    Returns:
        Database URL string for SQLAlchemy.
    """
    db_url = settings.database_url

    # Handle SQLite file path
    if db_url.startswith("sqlite:///"):
        db_path = Path(db_url.replace("sqlite:///", ""))

        # Ensure parent directory exists
        db_dir = db_path.parent
        if not db_dir.exists():
            # Try to create it, fallback to local directory if no permissions
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except PermissionError:
                # Fallback to local data directory
                local_dir = Path(__file__).parent.parent / "data"
                local_dir.mkdir(exist_ok=True)
                db_url = f"sqlite:///{local_dir}/thewallflower.db"
                logger.warning(
                    f"Could not create {db_dir}, using fallback: {db_url}"
                )

    return db_url


# Create engine with appropriate settings
_database_url = get_database_url()
engine = create_engine(
    _database_url,
    echo=settings.debug,  # SQL logging in debug mode
    connect_args={"check_same_thread": False}  # Required for SQLite with FastAPI
)

# Enable Write-Ahead Logging (WAL) for better concurrency
if _database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

logger.info(f"Database configured: {_database_url} (WAL Mode enabled)")


def init_db() -> None:
    """Initialize the database, creating all tables.

    This is idempotent - safe to call multiple times.
    Tables that already exist will not be recreated.
    """
    # Import models to ensure they're registered with SQLModel
    from app import models  # noqa: F401

    logger.info("Initializing database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database initialization complete")


def get_session() -> Generator[Session, None, None]:
    """Dependency that yields a database session.

    Usage:
        @app.get("/items")
        def get_items(session: Session = Depends(get_session)):
            ...

    Yields:
        Database session that auto-closes after request.
    """
    with Session(engine) as session:
        yield session