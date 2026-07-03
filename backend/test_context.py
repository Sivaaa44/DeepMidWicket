import os
import uuid
import json
import time
from agent import ask, use_redis, redis_client
from auth_database import get_session_state, get_recent_messages

def run_tests():
    print("Starting session context management verification tests...")
    print(f"Redis is active: {use_redis}")

    session_id = str(uuid.uuid4())
    print(f"Generated Session ID: {session_id}")

    # Query 1: Kohli stats
    print("\n--- Sending Query 1: 'what are Virat Kohli's stats?' ---")
    res1 = ask("what are Virat Kohli's stats?", session_id=session_id)
    print(f"Routed Tool: {res1['tool']}")
    print(f"Arguments: {res1['args']}")
    print(f"Answer: {res1['answer']}")

    # Verify ledger updates in Redis and SQLite
    if use_redis:
        try:
            r_ledger = redis_client.get(f"session:{session_id}:ledger")
            print(f"Redis Ledger Cache: {r_ledger}")
        except Exception as e:
            print(f"Error fetching from Redis: {e}")
    
    db_state = get_session_state(session_id)
    print(f"SQLite DB Ledger State: {db_state['ledger'] if db_state else 'None'}")
    
    # Query 2: pronoun match
    print("\n--- Sending Query 2: 'how is he compared to Rohit Sharma?' ---")
    res2 = ask("how is he compared to Rohit Sharma?", session_id=session_id)
    print(f"Routed Tool: {res2['tool']}")
    print(f"Arguments: {res2['args']}")
    print(f"Answer: {res2['answer']}")
    
    # Check messages in SQLite (wait brief moment to let BackgroundTasks finish if using API,
    # but here ask() is run directly, so we write to Redis cache. Raw message db writes are triggered in API.
    # We will simulate a quick save_message to verify SQLite.)
    from auth_database import save_message
    save_message(session_id, "user", "what are Virat Kohli's stats?")
    save_message(session_id, "assistant", res1['answer'])
    save_message(session_id, "user", "how is he compared to Rohit Sharma?")
    save_message(session_id, "assistant", res2['answer'])
    
    db_messages = get_recent_messages(session_id, limit=5)
    print(f"\nSQLite Message Logs count: {len(db_messages)}")
    for m in db_messages:
        print(f"  {m['role']}: {m['content']}")

    print("\nVerification tests complete!")

if __name__ == "__main__":
    run_tests()
