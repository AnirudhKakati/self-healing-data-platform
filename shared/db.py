from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from shared.config import DATABASE_URL, DATA_WAREHOUSE_URL
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine

asyncio_engine=create_async_engine(DATABASE_URL)

async_session=async_sessionmaker(bind=asyncio_engine,expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session

#we create a sync engine connection to the local postgres data warehouse DB
dw_engine=create_engine(DATA_WAREHOUSE_URL)