import time


from oci_runtime.adapters._cancellation import (
    CompositeCancellationToken,
    DeadlineCancellationToken,
    ThreadCancellationToken,
)


class TestThreadCancellationToken:
    def test_default_not_cancelled(self):
        t = ThreadCancellationToken()
        assert t.is_cancelled is False

    def test_cancel_sets_state(self):
        t = ThreadCancellationToken()
        t.cancel()
        assert t.is_cancelled is True

    def test_cancel_is_idempotent(self):
        t = ThreadCancellationToken()
        t.cancel()
        t.cancel()
        assert t.is_cancelled is True

    def test_cross_thread_visibility(self):
        import threading
        t = ThreadCancellationToken()
        def setter():
            t.cancel()
        thread = threading.Thread(target=setter)
        thread.start()
        thread.join()
        assert t.is_cancelled is True


class TestDeadlineCancellationToken:
    def test_default_not_cancelled(self):
        d = DeadlineCancellationToken(10.0)
        assert d.is_cancelled is False
        d.cancel()

    def test_fires_after_timeout(self):
        d = DeadlineCancellationToken(0.05)
        assert d.is_cancelled is False
        time.sleep(0.1)
        assert d.is_cancelled is True

    def test_cancel_disarms_timer(self):
        d = DeadlineCancellationToken(1.0)
        d.cancel()
        assert d.is_cancelled is True

    def test_cancel_before_timeout(self):
        d = DeadlineCancellationToken(0.5)
        d.cancel()
        time.sleep(0.1)
        assert d.is_cancelled is True


class TestCompositeCancellationToken:
    def test_default_not_cancelled(self):
        a = ThreadCancellationToken()
        b = ThreadCancellationToken()
        c = CompositeCancellationToken(a, b)
        assert c.is_cancelled is False

    def test_cancelled_when_any_child_cancelled(self):
        a = ThreadCancellationToken()
        b = ThreadCancellationToken()
        c = CompositeCancellationToken(a, b)
        b.cancel()
        assert c.is_cancelled is True
        assert a.is_cancelled is False

    def test_cancel_propagates_to_all_children(self):
        a = ThreadCancellationToken()
        b = ThreadCancellationToken()
        c = CompositeCancellationToken(a, b)
        c.cancel()
        assert a.is_cancelled is True
        assert b.is_cancelled is True

    def test_empty_composite_not_cancelled(self):
        c = CompositeCancellationToken()
        assert c.is_cancelled is False
