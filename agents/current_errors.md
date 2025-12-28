## current errors.

- on adding of a confirmed working RTSP stream the browser crashes totally. The test stream works, then you click add, then immidiet browser slowdown and crash. 

- there is an error with the wall flower container, the log is here:
  File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 439, in load

    self.loaded_app = import_from_string(self.app)

                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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

  File "/app/backend/app/main.py", line 26, in <module>

    from app.stream_manager import stream_manager

  File "/app/backend/app/stream_manager.py", line 25, in <module>

    from app.worker import (

ImportError: cannot import name 'CircuitBreakerState' from 'app.worker' (/app/backend/app/worker.py)

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

[INFO] Starting go2rtc...

[INFO] go2rtc started with PID 10

[INFO] Waiting for go2rtc... (attempt 1/30)

08:23:11.447 INF go2rtc platform=linux/amd64 revision=fa580c5 version=1.9.9

08:23:11.447 INF config path=/data/go2rtc.yaml

08:23:11.447 INF [api] listen addr=:1985

08:23:11.447 INF [rtsp] listen addr=:8654

08:23:11.448 INF [webrtc] listen addr=:8655

[INFO] go2rtc is ready on ports: API=1985, RTSP=8654, WebRTC=8655

[INFO] Starting TheWallflower...

[INFO] Application started with PID 20

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

  File "/app/backend/app/main.py", line 26, in <module>

    from app.stream_manager import stream_manager

  File "/app/backend/app/stream_manager.py", line 25, in <module>

    from app.worker import (

ImportError: cannot import name 'CircuitBreakerState' from 'app.worker' (/app/backend/app/worker.py)