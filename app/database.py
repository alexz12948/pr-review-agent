from sqlalchemy import inspect
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _add_missing_columns(conn):
    """Add columns present in the models but missing from existing tables.

    create_all() only creates missing tables; it never ALTERs existing ones, so
    columns added to a model (e.g. ReviewRecord.fix_actions_count) would be
    absent on a pre-existing DB and writes to them would raise OperationalError.
    This performs a lightweight, idempotent ADD COLUMN for each missing column,
    serving as a minimal migration step in lieu of a full framework like Alembic.
    """
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # newly created by create_all with all columns present
        existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            col_type = column.type.compile(dialect=conn.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
            default = column.default
            if default is not None and getattr(default, "is_scalar", False):
                value = default.arg
                if isinstance(value, bool):
                    value = 1 if value else 0
                elif isinstance(value, str):
                    value = "'" + value.replace("'", "''") + "'"
                ddl += f" DEFAULT {value}"
            conn.exec_driver_sql(ddl)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def get_db():
    async with async_session() as session:
        yield session
