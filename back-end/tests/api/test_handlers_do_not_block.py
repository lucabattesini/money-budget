"""TKT-107: a handler declared `async def` runs on the server's one event loop. Ours use a synchronous database
driver, so such a handler freezes every other request while it waits for a connection. With a small pool the requests that
hold the connections then cannot finish and give them back: the whole app stalls until the pool times out (30 s).

A handler may only be `async def` to `await` something (the request body, an upload). Its blocking work then goes through
`run_in_threadpool`, like the database and the model calls below.
"""

import ast
from pathlib import Path

ROUTERS = sorted(Path(__file__).resolve().parents[2].glob("api/routers/*_router.py"))


def _own_nodes(function):
    """The nodes of a function, without those of the functions defined inside it."""
    stack = list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _async_handlers():
    for path in ROUTERS:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.AsyncFunctionDef):
                yield path.name, node


def test_the_routers_were_found():
    assert len(ROUTERS) >= 10


def test_no_handler_is_async_unless_it_awaits():
    useless = [
        f"{name}:{node.lineno} {node.name}"
        for name, node in _async_handlers()
        if not any(isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith)) for n in _own_nodes(node))
    ]
    assert useless == [], "async handlers that never await block the event loop; make them plain `def`: " + ", ".join(
        useless
    )


def test_async_handlers_hand_blocking_work_to_the_threadpool():
    """The few handlers that stay async (they read the request body) must not touch the database or the network
    themselves: every call of the controllers goes through run_in_threadpool."""
    direct = []
    for name, node in _async_handlers():
        for call in (n for n in _own_nodes(node) if isinstance(n, ast.Call)):
            if isinstance(call.func, ast.Name) and call.func.id in _BLOCKING:
                direct.append(f"{name}:{call.lineno} {call.func.id}")
    assert direct == [], "called on the event loop, use `await run_in_threadpool(...)`: " + ", ".join(direct)


_BLOCKING = {
    "stage_import",
    "authenticate_access_token",
    "get_user_by_id_ctrl",
    "handle_message",
    "register_client",
    "exchange_token",
    "revoke_token",
    "process_whatsapp_message",
    "send_whatsapp_message",
}
