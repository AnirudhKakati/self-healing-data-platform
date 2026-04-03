import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL=os.getenv("DATABASE_URL")
DATABASE_URL_SYNC=os.getenv("DATABASE_URL_SYNC")
REDIS_URL=os.getenv("REDIS_URL")
ENV=os.getenv("ENV", "dev")