from worker.app.executor import run_executor_service 
from shared.redis_client import redis_client
import asyncio

QUEUE_NAME="pipeline_runs"

async def main():
    print("Worker is listening for pipeline runs...")

    while True:
        try:
            result=await redis_client.blpop(QUEUE_NAME)

            if result is None:
                continue

            queue_name,value=result
            run_id=int(value.decode("utf-8"))
            print(f"Picked up run_id={run_id} from {queue_name.decode('utf-8')}")

            try: 
                await run_executor_service(run_id)
            except Exception as e: #generic exception for now
                print(f"Failed to execute run_id={run_id} : {e}")
        
        except Exception as e: #generic exception for now
            print(f"Worker loop error: {e}")
            await asyncio.sleep(1)                        

if __name__=="__main__":
    asyncio.run(main())