from __future__ import annotations

import threading
import time
import unittest

from devflow.session import SessionManager


class RegisterAndLookupTests(unittest.TestCase):
    def test_register_and_lookup(self) -> None:
        mgr = SessionManager()
        mgr.register("oc_1", "ou_1", "run_001", "running")
        info = mgr.lookup("oc_1", "ou_1")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.run_id, "run_001")
        self.assertEqual(info.status, "running")

    def test_lookup_returns_none_for_unknown_session(self) -> None:
        mgr = SessionManager()
        self.assertIsNone(mgr.lookup("oc_x", "ou_x"))


class UnregisterTests(unittest.TestCase):
    def test_unregister_removes_entry(self) -> None:
        mgr = SessionManager()
        mgr.register("oc_1", "ou_1", "run_001", "running")
        mgr.unregister("oc_1", "ou_1")
        self.assertIsNone(mgr.lookup("oc_1", "ou_1"))

    def test_unregister_unknown_session_is_noop(self) -> None:
        mgr = SessionManager()
        mgr.unregister("oc_1", "ou_1")


class UpdateStatusTests(unittest.TestCase):
    def test_update_status_changes_status_and_refreshes_timestamp(self) -> None:
        mgr = SessionManager()
        mgr.register("oc_1", "ou_1", "run_001", "running")
        info_before = mgr.lookup("oc_1", "ou_1")
        assert info_before is not None
        ts_before = info_before.last_updated

        time.sleep(0.05)
        mgr.update_status("oc_1", "ou_1", "waiting_approval")

        info_after = mgr.lookup("oc_1", "ou_1")
        assert info_after is not None
        self.assertEqual(info_after.status, "waiting_approval")
        self.assertGreater(info_after.last_updated, ts_before)

    def test_update_status_raises_for_unknown_session(self) -> None:
        mgr = SessionManager()
        with self.assertRaises(KeyError):
            mgr.update_status("oc_x", "ou_x", "running")


class SessionTimeoutTests(unittest.TestCase):
    def test_lookup_returns_none_for_expired_session(self) -> None:
        mgr = SessionManager(session_timeout_seconds=1)
        mgr.register("oc_1", "ou_1", "run_001", "running")
        time.sleep(1.1)
        self.assertIsNone(mgr.lookup("oc_1", "ou_1"))

    def test_auto_cleanup_purges_expired_entries(self) -> None:
        mgr = SessionManager(session_timeout_seconds=1)
        mgr.register("oc_1", "ou_1", "run_001", "running")
        mgr.register("oc_2", "ou_2", "run_002", "running")
        time.sleep(1.1)

        mgr.register("oc_3", "ou_3", "run_003", "running")

        self.assertIsNone(mgr.lookup("oc_1", "ou_1"))
        self.assertIsNone(mgr.lookup("oc_2", "ou_2"))
        info = mgr.lookup("oc_3", "ou_3")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.run_id, "run_003")

    def test_non_expired_session_survives_cleanup(self) -> None:
        mgr = SessionManager(session_timeout_seconds=10)
        mgr.register("oc_1", "ou_1", "run_001", "running")
        info = mgr.lookup("oc_1", "ou_1")
        self.assertIsNotNone(info)


class ThreadSafetyTests(unittest.TestCase):
    def test_concurrent_register_lookup_unregister(self) -> None:
        mgr = SessionManager()
        errors: list[Exception] = []
        num_threads = 20
        barrier = threading.Barrier(num_threads)

        def worker(idx: int) -> None:
            try:
                chat_id = f"oc_{idx}"
                sender_id = f"ou_{idx}"
                barrier.wait(timeout=5)
                mgr.register(chat_id, sender_id, f"run_{idx}", "running")
                info = mgr.lookup(chat_id, sender_id)
                if info is None:
                    errors.append(AssertError(f"lookup returned None for {chat_id}:{sender_id}"))
                    return
                mgr.update_status(chat_id, sender_id, "success")
                info2 = mgr.lookup(chat_id, sender_id)
                if info2 is None or info2.status != "success":
                    errors.append(AssertError(f"status mismatch for {chat_id}:{sender_id}"))
                    return
                mgr.unregister(chat_id, sender_id)
                if mgr.lookup(chat_id, sender_id) is not None:
                    errors.append(AssertError(f"unregister failed for {chat_id}:{sender_id}"))
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(len(errors), 0, f"线程安全测试失败: {errors}")


if __name__ == "__main__":
    unittest.main()
