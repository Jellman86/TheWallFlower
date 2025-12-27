current errors:
The whisper live container log looks strange:

INFO:root:Single model mode currently only works with custom models.

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

Im not sure the containers are taking properly. Please review the code and the compose file.

2. There appears to be no way to modify the RTSP stream URL, could you create a comprehensve settings panel so we can modify the rtsp strams as well as other settings.
3. There appears to be no checking or error handeling on the RTSP streams. I entered an incorrect RTSP url and it seemed to crash the whole browser, an example RTSP stream that Im going to add is: rtsp://Jellman86:o7zlFClGhWL0l7@192.168.214.157/stream1
4. the transcriptions should be availble in the UI for each camera configured, they should also be able to be written to the local filesystem if configured in the stream settings.
5. please understand that YA-WAMF is a different project that is not connected to the wallflower. Please dont corss contaminate the code.