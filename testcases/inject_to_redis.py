import json
import os
import sys

# Import the worker functions safely
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from worker.ingestion_worker import extract_pool_payload, get_redis_client, REDIS_QUEUE_KEY

def inject_to_redis():
    input_file = "testcases/recent_tokens_data.json"
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    print("Connecting to Redis...")
    redis_client = get_redis_client()
    try:
        redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        sys.exit(1)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_injected = 0
    for network, pools in data.items():
        print(f"Injecting {len(pools)} pools for {network} into Redis...")
        for pool_data in pools:
            payload = extract_pool_payload(pool_data, network)
            redis_client.rpush(REDIS_QUEUE_KEY, json.dumps(payload))
            total_injected += 1

    print(f"\n✅ Total of {total_injected} pools injected into '{REDIS_QUEUE_KEY}'!")

if __name__ == "__main__":
    inject_to_redis()
