"""
End-to-end API tests with the LLM mocked out. Runs against a throwaway users DB
and the real cricket.db (read-only).

    cd backend && python -m unittest -v
"""
import os
import tempfile
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

_tmp = tempfile.mkdtemp()
os.environ["USERS_DB_PATH"] = os.path.join(_tmp, "users_test.db")
os.environ["LOG_DIR"] = os.path.join(_tmp, "logs")
os.environ["ADMIN_EMAILS"] = "admin@test.dev"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ.pop("REDIS_URL", None)
os.environ.pop("REDIS_HOST", None)

from fastapi.testclient import TestClient  # noqa: E402

import agent  # noqa: E402
import config  # noqa: E402
import memory  # noqa: E402
from auth_database import get_context_messages, get_session_state  # noqa: E402
from database import QueryError, run_query  # noqa: E402
from main import app  # noqa: E402

KOHLI_SQL = ("SELECT batter AS player, SUM(runs_batter) AS runs, "
             "COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END) AS balls "
             "FROM deliveries WHERE batter LIKE '%Kohli%' GROUP BY batter")


def _usage(i=100, o=20):
    return SimpleNamespace(prompt_tokens=i, completion_tokens=o)


def _tool_response(name, args):
    import json
    call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call], content=None))],
                           usage=_usage())


def _text_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None, content=text))],
                           usage=_usage())


class FakeLLM:
    """Scriptable stand-in for agent.llm_call."""

    def __init__(self):
        self.sql = [KOHLI_SQL]
        self.calls = []
        self.fail_stage = None

    def __call__(self, usage, stage, **kwargs):
        self.calls.append((stage, kwargs))
        if stage == self.fail_stage:
            raise agent.AgentError("llm_rate_limited", "The AI service is busy right now.", "429")
        if stage == "route":
            question = kwargs["messages"][-1]["content"].lower()
            if "hello" in question:
                resp = _tool_response("general_chat", {"question": question})
            elif "his" in question:
                resp = _tool_response("player_stats", {"player_name": "Kohli", "stat_type": "batting", "phase": "death"})
            else:
                resp = _tool_response("player_stats", {"player_name": "Kohli", "stat_type": "batting", "phase": "overall"})
        elif stage == "sql":
            resp = _text_response(self.sql.pop(0) if len(self.sql) > 1 else self.sql[0])
        elif stage == "summary":
            resp = _text_response("User explored Virat Kohli's batting.")
        else:
            resp = _text_response("**V Kohli** leads with plenty of runs.")
        usage.add(resp.usage)
        return resp


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.llm = FakeLLM()
        patcher = mock.patch.object(agent, "llm_call", self.llm)
        patcher.start()
        self.addCleanup(patcher.stop)

    def signup(self, email=None, username=None):
        email = email or f"u{uuid.uuid4().hex[:8]}@test.dev"
        username = username or f"user_{uuid.uuid4().hex[:8]}"
        r = self.client.post("/auth/signup", json={"email": email, "username": username, "password": "password123"})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


class TestAuth(ApiTestCase):
    def test_signup_login_me(self):
        email = f"Mixed{uuid.uuid4().hex[:6]}@Test.dev"
        headers, user = self.signup(email=email)
        self.assertEqual(user["email"], email.lower())
        r = self.client.post("/auth/login", json={"email": email.upper(), "password": "password123"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        self.assertEqual(r.status_code, 401)
        me = self.client.get("/auth/me", headers=headers).json()
        self.assertEqual(me["usage"]["limit"], config.DEFAULT_MONTHLY_TOKEN_LIMIT)
        self.assertFalse(me["is_admin"])

    def test_invalid_token_is_rejected_not_downgraded(self):
        r = self.client.get("/sessions", headers={"Authorization": "Bearer not-a-jwt"})
        self.assertEqual(r.status_code, 401)

    def test_weak_password_rejected(self):
        r = self.client.post("/auth/signup", json={"email": "x@y.dev", "username": "xyz", "password": "short"})
        self.assertEqual(r.status_code, 400)


class TestAskAndSessions(ApiTestCase):
    def test_turn_is_persisted_with_snapshot(self):
        headers, _ = self.signup()
        r = self.client.post("/ask", json={"question": "Virat Kohli batting stats"}, headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIsNone(body["error"])
        self.assertEqual(body["tool"], "player_stats")
        self.assertGreater(body["tokens"]["total"], 0)
        self.assertIn("remaining", body["quota"])
        sid = body["session_id"]

        sessions = self.client.get("/sessions", headers=headers).json()["sessions"]
        self.assertEqual(sessions[0]["id"], sid)
        self.assertEqual(sessions[0]["title"], "Virat Kohli batting stats")
        self.assertIsNotNone(sessions[0]["created_at"])

        msgs = self.client.get(f"/sessions/{sid}/messages", headers=headers).json()["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        self.assertEqual(msgs[1]["data"]["columns"], ["player", "runs", "balls"])
        self.assertTrue(msgs[1]["data"]["rows"])
        self.assertIn("Kohli", msgs[1]["sql"])

    def test_follow_up_sees_previous_turn_and_ledger(self):
        headers, _ = self.signup()
        sid = self.client.post("/ask", json={"question": "Virat Kohli batting stats"}, headers=headers).json()["session_id"]
        self.client.post("/ask", json={"question": "and his death overs?", "session_id": sid}, headers=headers)
        route_prompts = [kw["messages"][0]["content"] for stage, kw in self.llm.calls if stage == "route"]
        self.assertIn("Virat Kohli batting stats", route_prompts[-1])
        self.assertIn("V Kohli", route_prompts[-1])  # ledger resolved from args/question
        ledger = memory.normalize_ledger(get_session_state(sid)["ledger"])
        self.assertEqual(ledger["people"][0], "V Kohli")

    def test_other_users_cannot_use_or_read_a_session(self):
        a_headers, _ = self.signup()
        b_headers, _ = self.signup()
        sid = self.client.post("/ask", json={"question": "Kohli stats"}, headers=a_headers).json()["session_id"]
        self.assertEqual(self.client.get(f"/sessions/{sid}/messages", headers=b_headers).status_code, 404)
        self.assertEqual(self.client.post("/ask", json={"question": "x", "session_id": sid}, headers=b_headers).status_code, 404)
        self.assertEqual(self.client.delete(f"/sessions/{sid}", headers=b_headers).status_code, 404)
        self.assertEqual(self.client.get(f"/sessions/{sid}/messages").status_code, 404)  # anonymous

    def test_rename_and_delete(self):
        headers, _ = self.signup()
        sid = self.client.post("/ask", json={"question": "Kohli stats"}, headers=headers).json()["session_id"]
        r = self.client.patch(f"/sessions/{sid}", json={"title": "  Kohli   deep dive "}, headers=headers)
        self.assertEqual(r.json()["title"], "Kohli deep dive")
        self.assertEqual(self.client.delete(f"/sessions/{sid}", headers=headers).status_code, 200)
        self.assertIsNone(get_session_state(sid))

    def test_sql_repair_retry(self):
        headers, _ = self.signup()
        self.llm.sql = ["SELECT nope FROM missing_table", KOHLI_SQL]
        body = self.client.post("/ask", json={"question": "Kohli stats"}, headers=headers).json()
        self.assertIsNone(body["error"])
        self.assertEqual(sum(1 for s, _ in self.llm.calls if s == "sql"), 2)

    def test_failed_turn_is_recorded_but_kept_out_of_context(self):
        headers, _ = self.signup()
        self.llm.fail_stage = "answer"
        body = self.client.post("/ask", json={"question": "Kohli stats"}, headers=headers).json()
        self.assertEqual(body["error"]["code"], "llm_rate_limited")
        self.assertNotIn("detail", body["error"])
        self.assertGreater(body["tokens"]["total"], 0)  # route + sql tokens are still accounted
        sid = body["session_id"]
        msgs = self.client.get(f"/sessions/{sid}/messages", headers=headers).json()["messages"]
        self.assertTrue(msgs[1]["is_error"])
        self.assertEqual(get_context_messages(sid, 10), [])

    def test_anonymous_quota_is_persisted(self):
        with mock.patch.object(config, "ANON_QUERY_LIMIT", 2):
            client = TestClient(app, client=("10.9.8.7", 5000))
            for _ in range(2):
                self.assertEqual(client.post("/ask", json={"question": "hello"}).status_code, 200)
            r = client.post("/ask", json={"question": "hello"})
            self.assertEqual(r.status_code, 429)
            self.assertEqual(r.json()["detail"]["code"], "quota_exceeded")

    def test_user_token_quota(self):
        headers, user = self.signup()
        from auth_database import update_user
        update_user(user["id"], monthly_token_limit=1)
        self.client.post("/ask", json={"question": "hello"}, headers=headers)
        self.assertEqual(self.client.post("/ask", json={"question": "hello"}, headers=headers).status_code, 429)

    def test_stream_endpoint(self):
        headers, _ = self.signup()
        with self.client.stream("POST", "/ask/stream", json={"question": "Kohli stats"}, headers=headers) as r:
            text = "".join(r.iter_text())
        self.assertIn("event: session", text)
        self.assertIn('"stage": "route"', text)
        self.assertIn("event: result", text)

    def test_rolling_summary_without_redis(self):
        headers, _ = self.signup()
        with mock.patch.object(config, "HOT_WINDOW_MESSAGES", 2), mock.patch.object(config, "SUMMARIZE_BATCH_MESSAGES", 2):
            sid = None
            for q in ["Kohli stats", "Kohli again", "Kohli once more"]:
                body = self.client.post("/ask", json={"question": q, "session_id": sid}, headers=headers).json()
                sid = body["session_id"]
            for _ in range(50):
                state = get_session_state(sid)
                if state["summary"]:
                    break
                time.sleep(0.05)
        self.assertEqual(state["summary"], "User explored Virat Kohli's batting.")
        self.assertGreater(state["summarized_upto"], 0)


class TestAdmin(ApiTestCase):
    def test_admin_access_and_user_management(self):
        user_headers, user = self.signup()
        self.assertEqual(self.client.get("/admin/overview", headers=user_headers).status_code, 403)
        self.assertEqual(self.client.get("/admin/overview").status_code, 403)

        admin_headers, admin = self.signup(email="admin@test.dev", username="admin_user")
        self.assertTrue(admin["is_admin"])
        self.client.post("/ask", json={"question": "Kohli stats"}, headers=user_headers)

        ov = self.client.get("/admin/overview?days=7", headers=admin_headers).json()
        self.assertEqual(len(ov["daily"]), 7)
        self.assertGreaterEqual(ov["kpis"]["questions"], 1)
        self.assertEqual(self.client.get("/admin/system", headers=admin_headers).status_code, 200)
        self.assertGreaterEqual(self.client.get("/admin/activity", headers=admin_headers).json()["total"], 1)

        r = self.client.patch(f"/admin/users/{user['id']}", json={"monthly_token_limit": 1234}, headers=admin_headers)
        self.assertEqual(r.json()["monthly_token_limit"], 1234)
        self.client.patch(f"/admin/users/{user['id']}", json={"is_active": False}, headers=admin_headers)
        self.assertEqual(self.client.get("/auth/me", headers=user_headers).status_code, 403)

        r = self.client.patch(f"/admin/users/{admin['id']}", json={"is_admin": False}, headers=admin_headers)
        self.assertEqual(r.status_code, 400)


class TestUnits(unittest.TestCase):
    def test_ledger_keeps_most_recent_first(self):
        ledger = memory.empty_ledger()
        for name in ["A", "B", "C", "D", "E", "F", "B"]:
            ledger = memory.merge_ledger(ledger, {"people": [name]})
        self.assertEqual(ledger["people"], ["B", "F", "E", "D", "C"])

    def test_run_query_is_read_only(self):
        _, cols, rows = run_query("WITH x AS (SELECT 1 AS n) SELECT n FROM x")
        self.assertEqual((cols, rows), (["n"], [{"n": 1}]))
        for bad in ["DELETE FROM matches", "SELECT 1; DROP TABLE matches", ""]:
            with self.assertRaises(QueryError):
                run_query(bad)

    def test_sanitise_strips_like_wildcards(self):
        self.assertEqual(agent.sanitise("Ko'hli%_"), "Kohli")


if __name__ == "__main__":
    unittest.main()
