import unittest
import uuid

from auth_database import (
    create_user,
    save_message,
    get_user_sessions,
    get_recent_messages,
    update_session_title,
    delete_session_db,
    get_session_state,
)

class TestSessionHistory(unittest.TestCase):
    def test_session_creation_and_auto_title(self):
        user = create_user(f"u_{uuid.uuid4()}@test.com", f"user_{uuid.uuid4()}", "hash")
        user_id = user["id"]
        session_id = f"test-session-{uuid.uuid4()}"

        # Save first user message
        save_message(session_id, "user", "What are Virat Kohli's stats in IPL?", user_id=user_id)
        save_message(session_id, "assistant", "Virat Kohli has scored 8000+ runs.", user_id=user_id)

        # Retrieve sessions for user_id
        sessions = get_user_sessions(user_id=user_id, limit=10)
        self.assertTrue(len(sessions) > 0)
        matched = [s for s in sessions if s["id"] == session_id]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["title"], "What are Virat Kohli's stats in IPL?")
        self.assertEqual(matched[0]["last_message_preview"], "Virat Kohli has scored 8000+ runs.")

    def test_session_ownership_isolation(self):
        user_a_obj = create_user(f"ua_{uuid.uuid4()}@test.com", f"usera_{uuid.uuid4()}", "hash")
        user_b_obj = create_user(f"ub_{uuid.uuid4()}@test.com", f"userb_{uuid.uuid4()}", "hash")
        user_a = user_a_obj["id"]
        user_b = user_b_obj["id"]

        sess_a = f"session-userA-{uuid.uuid4()}"
        sess_b = f"session-userB-{uuid.uuid4()}"
        sess_anon = f"session-anon-{uuid.uuid4()}"

        ip_anon = f"192.168.1.{uuid.uuid4().int % 250}"

        save_message(sess_a, "user", "User A question", user_id=user_a)
        save_message(sess_b, "user", "User B question", user_id=user_b)
        save_message(sess_anon, "user", "Anon question", anon_ip=ip_anon)

        # User A list
        list_a = get_user_sessions(user_id=user_a)
        ids_a = [s["id"] for s in list_a]
        self.assertIn(sess_a, ids_a)
        self.assertNotIn(sess_b, ids_a)
        self.assertNotIn(sess_anon, ids_a)

        # User B list
        list_b = get_user_sessions(user_id=user_b)
        ids_b = [s["id"] for s in list_b]
        self.assertIn(sess_b, ids_b)
        self.assertNotIn(sess_a, ids_b)

        # Anon list
        list_anon = get_user_sessions(anon_ip=ip_anon)
        ids_anon = [s["id"] for s in list_anon]
        self.assertIn(sess_anon, ids_anon)
        self.assertNotIn(sess_a, ids_anon)

    def test_session_rename_and_delete(self):
        user_obj = create_user(f"u_ren_{uuid.uuid4()}@test.com", f"user_ren_{uuid.uuid4()}", "hash")
        user_other = create_user(f"u_oth_{uuid.uuid4()}@test.com", f"user_oth_{uuid.uuid4()}", "hash")
        user_id = user_obj["id"]
        other_id = user_other["id"]

        session_id = f"test-rename-{uuid.uuid4()}"

        save_message(session_id, "user", "Original Question", user_id=user_id)

        # Attempt unauthorized rename by wrong user
        success_fail = update_session_title(session_id, "Hacked Title", user_id=other_id)
        self.assertFalse(success_fail)

        # Authorized rename
        success_pass = update_session_title(session_id, "New Custom Title", user_id=user_id)
        self.assertTrue(success_pass)

        state = get_session_state(session_id)
        self.assertEqual(state["title"], "New Custom Title")

        # Delete session
        del_success = delete_session_db(session_id, user_id=user_id)
        self.assertTrue(del_success)

        state_after = get_session_state(session_id)
        self.assertIsNone(state_after)
        messages_after = get_recent_messages(session_id)
        self.assertEqual(len(messages_after), 0)

if __name__ == "__main__":
    unittest.main()

