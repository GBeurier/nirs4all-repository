"""Test-only subprocess runner; production never accepts these unsafe profiles."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import uvicorn

from nirs4all_repository.project_service import ProjectService, create_app, serve

credentials, store, port, profile, seen = sys.argv[1:]
app = create_app(Path(store), Path(credentials))


class FaultService(ProjectService):
    async def _http(self, scope, receive):
        # Exercise the production exception boundary with a simulated owner failure
        # carrying the genuine query token and sentinel. No data is ever logged here.
        if scope["path"] == "/boom":
            raise RuntimeError(os.environ["N4R_TEST_FAILURE"])
        return await super()._http(scope, receive)


app.__class__ = FaultService


async def observed(scope, receive, send):
    with open(seen, "a") as stream:
        stream.write(scope["type"] + "\n")
    await app(scope, receive, send)


if profile == "A":
    serve(observed, host="127.0.0.1", port=int(port))
else:
    options = {"access_log": False, "log_level": "warning", "proxy_headers": False, "server_header": False, "http": "h11", "ws": "none", "loop": "asyncio"}
    options.update({
        "B": {"access_log": True, "log_level": "info"},
        "C": {"log_level": "info"},
        "D": {"log_level": "info", "ws": "websockets"},
        "E": {"ws": "websockets"},
        "F": {"log_level": "trace"},
        "G": {"log_config": None},
        "H": {},
        "I": {"http": "httptools"},
    }[profile])
    if profile == "H":
        config = uvicorn.Config(observed, host="127.0.0.1", port=int(port), **options)
        logging.getLogger("uvicorn.access").addHandler(logging.StreamHandler(sys.stderr))
        uvicorn.Server(config).run()
    else:
        uvicorn.run(observed, host="127.0.0.1", port=int(port), **options)
