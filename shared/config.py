import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL=os.getenv("DATABASE_URL")
DATABASE_URL_SYNC=os.getenv("DATABASE_URL_SYNC")
REDIS_URL=os.getenv("REDIS_URL")
ENV=os.getenv("ENV", "dev")
DATA_WAREHOUSE_URL=os.getenv("DATA_WAREHOUSE_URL") #local data warehouse url (2nd DB on postgres)
API_KEY_SECRET=os.getenv("API_KEY_SECRET")
ADMIN_SECRET_KEY=os.getenv("ADMIN_SECRET_KEY")