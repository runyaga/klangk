"""Additional tests for cli/client.py paths not covered yet."""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bark_backend.cli.config import CLIConfig


@pytest.fixture(autouse=True)
def reset_stdin_stdout():
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    yield
    sys.stdin = orig_stdin
    sys.stdout = orig_stdout


class TestWsShell:
    @pytest.mark.asyncio
    async def test_ws_shell_connection_failure_raises(self):
        from bark_backend.cli.client import _ws_shell

        ws_mock = MagicMock()

        async def fake_enter(self):
            return ws_mock

        async def fake_exit(self, *args):
            return None

        ws_mock.__aenter__ = fake_enter
        ws_mock.__aexit__ = fake_exit
        ws_mock.recv = AsyncMock(
            return_value=json.dumps(
                {"type": "not_workspace_ready", "data": "oops"}
            )
        )
        ws_mock.send = AsyncMock()

        with patch("websockets.connect", return_value=ws_mock):
            with pytest.raises(ConnectionError):
                await _ws_shell("ws://localhost/ws", "token", "ws1")

    @pytest.mark.asyncio
    async def test_ws_shell_success_sends_connect_and_start(self):
        from bark_backend.cli.client import _ws_shell

        ws_mock = MagicMock()

        async def fake_enter(self):
            return ws_mock

        async def fake_exit(self, *args):
            return None

        ws_mock.__aenter__ = fake_enter
        ws_mock.__aexit__ = fake_exit
        ws_mock.send = AsyncMock()
        ws_mock.recv = AsyncMock(
            side_effect=[
                json.dumps({"type": "workspace_ready", "workspaceId": "ws1"}),
                json.dumps(
                    {"type": "terminal_output", "data": "\x1b[2J\x1b[H"}
                ),
                Exception("stop"),
            ]
        )

        with patch("websockets.connect", return_value=ws_mock):
            with patch("termios.tcgetattr", return_value=None):
                with patch("termios.tcsetattr"):
                    with patch("tty.setraw"):
                        try:
                            await _ws_shell(
                                "ws://localhost/ws", "token", "ws1"
                            )
                        except Exception:
                            pass

        sent = [c[0][0] for c in ws_mock.send.call_args_list]
        assert any("workspace_connect" in s for s in sent)
        assert any("terminal_start" in s for s in sent)


class TestRunShell:
    @pytest.mark.asyncio
    async def test_stdout_loop_bytes_message(self):
        from bark_backend.cli.client import _run_shell

        ws = AsyncMock()
        ws.recv = AsyncMock(
            side_effect=[
                b'{"type": "terminal_output", "data": "raw-bytes"}',
                json.dumps(
                    {
                        "type": "event",
                        "event": {
                            "type": "CUSTOM",
                            "name": "container_stopped",
                            "value": {},
                        },
                    }
                ),
            ]
        )

        captured = []

        class CaptureWriter:
            def write(self, data):
                captured.append(data)

            def flush(self):
                pass

        orig_stdout = sys.stdout
        sys.stdout = CaptureWriter()
        task = asyncio.create_task(_run_shell(ws, 80, 24))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            sys.stdout = orig_stdout

        assert "raw-bytes" in "".join(captured)

    @pytest.mark.asyncio
    async def test_stdout_loop_ignores_unknown_event(self):
        from bark_backend.cli.client import _run_shell

        ws = AsyncMock()
        ws.recv = AsyncMock(
            side_effect=[
                json.dumps(
                    {
                        "type": "event",
                        "event": {"type": "RUN_STARTED", "value": {}},
                    }
                ),
                json.dumps(
                    {
                        "type": "event",
                        "event": {
                            "type": "CUSTOM",
                            "name": "container_stopped",
                            "value": {},
                        },
                    }
                ),
            ]
        )
        task = asyncio.create_task(_run_shell(ws, 80, 24))
        await asyncio.sleep(0.3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stdin_loop_broken_pipe(self):
        from bark_backend.cli.client import _run_shell

        ws = AsyncMock()
        ws.send = AsyncMock()
        ws.recv = AsyncMock(
            side_effect=[
                json.dumps(
                    {
                        "type": "event",
                        "event": {
                            "type": "CUSTOM",
                            "name": "container_stopped",
                            "value": {},
                        },
                    }
                )
            ]
        )

        sys.stdin = MagicMock()
        sys.stdin.buffer = MagicMock()
        sys.stdin.buffer.read = MagicMock(side_effect=BrokenPipeError)
        ws.recv = AsyncMock(
            side_effect=[
                json.dumps(
                    {
                        "type": "event",
                        "event": {
                            "type": "CUSTOM",
                            "name": "container_stopped",
                            "value": {},
                        },
                    }
                )
            ]
        )

        task = asyncio.create_task(_run_shell(ws, 80, 24))
        await asyncio.sleep(0.1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_resize_loop_sends_on_size_change(self):
        """resize_loop detects size change and sends terminal_resize via _send_resize."""
        from bark_backend.cli import client as cli_client
        from io import BytesIO, StringIO

        # Replace stdin with a non-blocking mock so stdin_loop exits fast.
        fake_stdin = StringIO("")
        sys.stdin = fake_stdin
        sys.stdin.buffer = BytesIO(b"")

        ws = AsyncMock()
        ws.send = AsyncMock()

        # recv blocks until stop_event is set; we keep it alive long enough
        # for resize_loop's 1s sleep to fire.
        async def slow_recv():
            await asyncio.sleep(5.0)  # enough time for resize_loop's 1s check
            return json.dumps(
                {
                    "type": "event",
                    "event": {
                        "type": "CUSTOM",
                        "name": "container_stopped",
                        "value": {},
                    },
                }
            )

        ws.recv = slow_recv

        orig_fn = cli_client._get_terminal_size
        call_idx = [0]

        def cycling_size():
            # First call = initial size (80,24). Second call = different size.
            call_idx[0] += 1
            return (120, 40) if call_idx[0] > 1 else (80, 24)

        cli_client._get_terminal_size = cycling_size

        task = asyncio.create_task(cli_client._run_shell(ws, 80, 24))
        await asyncio.sleep(2.5)  # resize_loop sleeps 1s, then sends resize
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            cli_client._get_terminal_size = orig_fn

        resize_msgs = [
            c[0][0]
            for c in ws.send.call_args_list
            if "terminal_resize" in c[0][0]
        ]
        assert len(resize_msgs) >= 1, (
            f"Expected at least 1 resize send, got {ws.send.call_count} total "
            f"sends: {[c[0][0] for c in ws.send.call_args_list]}"
        )


class TestAuthLines:
    def test_logout_network_error_propagates(self, tmp_path, monkeypatch):
        from bark_backend.cli import auth

        config_path = tmp_path / "cli.toml"
        monkeypatch.setattr(
            "bark_backend.cli.config._CONFIG_PATH", config_path
        )
        cfg = CLIConfig()
        cfg.server.url = "http://localhost:8997"
        cfg.auth.token = "tok"
        cfg.auth.email = "x@y.com"
        cfg.save()

        with patch("httpx.post", side_effect=OSError("no route")):
            with pytest.raises(OSError):
                auth.logout()

        # Token was cleared and saved before the server call.
        cfg2 = CLIConfig.load()
        assert cfg2.auth.token is None


class TestClientLines:
    def test_delete_workspace_500_exit(self):
        from bark_backend.cli.client import BarkClient

        cfg = CLIConfig()
        cfg.auth.token = "tok"
        client = BarkClient(cfg)

        list_resp = MagicMock()
        list_resp.status_code = 200
        list_resp.json.return_value = [
            {"id": "ws1", "name": "ws1", "created_at": "2025-01-01T00:00:00Z"}
        ]
        del_resp = MagicMock()
        del_resp.status_code = 500
        del_resp.text = "server error"
        del_resp.is_success = False

        with patch.object(client, "get", return_value=list_resp):
            with patch.object(client, "delete", return_value=del_resp):
                with pytest.raises(SystemExit):
                    client.delete_workspace("ws1")
