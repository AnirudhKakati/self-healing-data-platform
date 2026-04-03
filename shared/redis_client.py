from redis.asyncio import from_url
from shared.config import REDIS_URL

redis_client=from_url(REDIS_URL)