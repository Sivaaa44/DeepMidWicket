import unittest
import uuid
import json

from auth_database import (
    create_user,
    save_message,
    get_recent_messages,
    delete_session_db,
    get_session_state,
)

class TestMessageArtifacts(unittest.TestCase):
    def test_message_artifact_saving_and_retrieval(self):
        user = create_user(f"u_art_{uuid.uuid4()}@test.com", f"user_art_{uuid.uuid4()}", "hash")
        user_id = user["id"]
        session_id = f"test-artifact-{uuid.uuid4()}"

        question = "What are Kohli's powerplay stats?"
        answer = "Virat Kohli has scored 2500 runs in powerplay."
        tool = "player_stats"
        args = {"player_name": "Virat Kohli", "stat_type": "batting", "phase": "powerplay"}
        sql = "SELECT batter AS player, SUM(runs_batter) AS runs FROM deliveries WHERE over BETWEEN 0 AND 5 AND batter LIKE '%Kohli%';"
        data = {
            "columns": ["player", "runs", "balls_faced", "strike_rate"],
            "rows": [
                {"player": "V Kohli", "runs": 2500, "balls_faced": 1900, "strike_rate": 131.58}
            ]
        }

        # 1. Save user question
        save_message(session_id, "user", question, user_id=user_id)

        # 2. Save assistant answer with artifact data
        save_message(
            session_id,
            "assistant",
            answer,
            user_id=user_id,
            tool=tool,
            args=args,
            sql=sql,
            data=data
        )

        # 3. Retrieve messages for session
        messages = get_recent_messages(session_id)
        self.assertEqual(len(messages), 2)

        user_msg = messages[0]
        ast_msg = messages[1]

        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], question)

        self.assertEqual(ast_msg["role"], "assistant")
        self.assertEqual(ast_msg["content"], answer)
        self.assertEqual(ast_msg["tool"], tool)
        self.assertEqual(ast_msg["args"], args)
        self.assertEqual(ast_msg["sql"], sql)
        self.assertIsNotNone(ast_msg["data"])
        self.assertEqual(ast_msg["data"]["columns"], data["columns"])
        self.assertEqual(ast_msg["data"]["rows"], data["rows"])

    def test_artifact_deletion_cascade(self):
        user = create_user(f"u_del_{uuid.uuid4()}@test.com", f"user_del_{uuid.uuid4()}", "hash")
        user_id = user["id"]
        session_id = f"test-del-{uuid.uuid4()}"

        save_message(session_id, "user", "Hello", user_id=user_id)
        save_message(
            session_id,
            "assistant",
            "Hi there!",
            user_id=user_id,
            tool="general_chat",
            args={},
            sql=None,
            data={"columns": [], "rows": []}
        )

        # Delete session
        success = delete_session_db(session_id, user_id=user_id)
        self.assertTrue(success)

        messages = get_recent_messages(session_id)
        self.assertEqual(len(messages), 0)

if __name__ == "__main__":
    unittest.main()
