the wallflower container log is showing:

Actions

      

  File "/usr/local/lib/python3.11/asyncio/runners.py", line 118, in run

    return self._loop.run_until_complete(task)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete

  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 71, in serve

    await self._serve(sockets)

  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 78, in _serve

    config.load()

  File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 439, in load

    self.loaded_app = import_from_string(self.app)

                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 22, in import_from_string

    raise exc from None

  File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 19, in import_from_string

    module = importlib.import_module(module_str)

             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/importlib/__init__.py", line 126, in import_module

    return _bootstrap._gcd_import(name[level:], package, level)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "<frozen importlib._bootstrap>", line 1204, in _gcd_import

  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load

  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked

  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked

  File "<frozen importlib._bootstrap_external>", line 940, in exec_module

  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed

  File "/app/backend/app/main.py", line 16, in <module>

    from app.config import settings

ModuleNotFoundError: No module named 'app'

  ╔═══════════════════════════════════════╗

  ║         TheWallflower NVR             ║

  ║    Self-hosted NVR with Speech-to-Text ║

  ╚═══════════════════════════════════════╝

[INFO] Configuration:

[INFO]   DATABASE_URL: sqlite:///data/thewallflower.db

[INFO]   WHISPER_HOST: whisper-live

[INFO]   WHISPER_PORT: 9090

[INFO]   LOG_LEVEL: INFO

[INFO]   WORKERS: 1

[INFO] Waiting for WhisperLive at whisper-live:9090...

[INFO] WhisperLive is available

[INFO] Initializing database...

[WARN] Database initialization will happen on first request

[INFO] Starting TheWallflower...

[INFO] Application started with PID 10

Traceback (most recent call last):

  File "/usr/local/bin/uvicorn", line 8, in <module>

    sys.exit(main())

             ^^^^^^

  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1485, in __call__

    return self.main(*args, **kwargs)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1406, in main

    rv = self.invoke(ctx)

         ^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1269, in invoke

    return ctx.invoke(self.callback, **ctx.params)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/click/core.py", line 824, in invoke

    return callback(*args, **kwargs)

           ^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/uvicorn/main.py", line 424, in main

    run(

  File "/usr/local/lib/python3.11/site-packages/uvicorn/main.py", line 594, in run

    server.run()

  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 67, in run

    return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/uvicorn/_compat.py", line 30, in asyncio_run

    return runner.run(main)

           ^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/asyncio/runners.py", line 118, in run

    return self._loop.run_until_complete(task)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete

  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 71, in serve

    await self._serve(sockets)

  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 78, in _serve

    config.load()

  File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 439, in load

    self.loaded_app = import_from_string(self.app)

                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 22, in import_from_string

    raise exc from None

  File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 19, in import_from_string

    module = importlib.import_module(module_str)

             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/importlib/__init__.py", line 126, in import_module

    return _bootstrap._gcd_import(name[level:], package, level)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "<frozen importlib._bootstrap>", line 1204, in _gcd_import

  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load

  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked

  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked

  File "<frozen importlib._bootstrap_external>", line 940, in exec_module

  File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed

  File "/app/backend/app/main.py", line 16, in <module>

    from app.config import settings

ModuleNotFoundError: No module named 'app'

Whisperlive container logs are showing:

    

EOFError: stream ends after 0 bytes, before end of line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/server.py", line 545, in parse

    request = yield from Request.parse(

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 140, in parse

    raise EOFError("connection closed while reading HTTP request line") from exc

EOFError: connection closed while reading HTTP request line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 590, in conn_handler

    connection.handshake(

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 189, in handshake

    raise self.protocol.handshake_exc

websockets.exceptions.InvalidMessage: did not receive a valid HTTP request

ERROR:websockets.server:opening handshake failed

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 138, in parse

    request_line = yield from parse_line(read_line)

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 309, in parse_line

    line = yield from read_line(MAX_LINE_LENGTH)

  File "/usr/local/lib/python3.10/dist-packages/websockets/streams.py", line 46, in read_line

    raise EOFError(f"stream ends after {p} bytes, before end of line")

EOFError: stream ends after 0 bytes, before end of line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/server.py", line 545, in parse

    request = yield from Request.parse(

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 140, in parse

    raise EOFError("connection closed while reading HTTP request line") from exc

EOFError: connection closed while reading HTTP request line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 590, in conn_handler

    connection.handshake(

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 189, in handshake

    raise self.protocol.handshake_exc

websockets.exceptions.InvalidMessage: did not receive a valid HTTP request

ERROR:websockets.server:opening handshake failed

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 138, in parse

    request_line = yield from parse_line(read_line)

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 309, in parse_line

    line = yield from read_line(MAX_LINE_LENGTH)

  File "/usr/local/lib/python3.10/dist-packages/websockets/streams.py", line 46, in read_line

    raise EOFError(f"stream ends after {p} bytes, before end of line")

EOFError: stream ends after 0 bytes, before end of line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/server.py", line 545, in parse

    request = yield from Request.parse(

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 140, in parse

    raise EOFError("connection closed while reading HTTP request line") from exc

EOFError: connection closed while reading HTTP request line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 590, in conn_handler

    connection.handshake(

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 189, in handshake

    raise self.protocol.handshake_exc

websockets.exceptions.InvalidMessage: did not receive a valid HTTP request

ERROR:websockets.server:opening handshake failed

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 138, in parse

    request_line = yield from parse_line(read_line)

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 309, in parse_line

    line = yield from read_line(MAX_LINE_LENGTH)

  File "/usr/local/lib/python3.10/dist-packages/websockets/streams.py", line 46, in read_line

    raise EOFError(f"stream ends after {p} bytes, before end of line")

EOFError: stream ends after 0 bytes, before end of line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/server.py", line 545, in parse

    request = yield from Request.parse(

  File "/usr/local/lib/python3.10/dist-packages/websockets/http11.py", line 140, in parse

    raise EOFError("connection closed while reading HTTP request line") from exc

EOFError: connection closed while reading HTTP request line

The above exception was the direct cause of the following exception:

Traceback (most recent call last):

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 590, in conn_handler

    connection.handshake(

  File "/usr/local/lib/python3.10/dist-packages/websockets/sync/server.py", line 189, in handshake

    raise self.protocol.handshake_exc

websockets.exceptions.InvalidMessage: did not receive a valid HTTP request