# PR-1 Self-Review: Add unit tests for CLI api_server command argument parsing

## What I changed and why

I added a new test file `test_api_server_arg_parsing.py` with 22 unit tests that check how the `api-server` CLI subcommand parses its arguments. The tests cover:

- **--port / -p**: Parses to integer correctly and rejects non-integer input
- **--workers / -w**: Same for workers
- **--apps**: Accepts `all`, `core`, `execution`, comma-separated values; defaults to `all`
- **--host / -H**: Accepts hostname/IP strings
- **--worker-timeout / -t**: Integer, defaults to 120, rejects non-integer
- **--proxy-headers**: Boolean flag, defaults to False
- **--dev / -d**: Boolean flag, defaults to False
- **--ssl-cert / --ssl-key**: File path strings
- **--log-config**: File path strings
- I also added combined flags and a parametrized combination test

## Why unit tests here

I went with unit tests because we're only testing argument parsing. No server, database, or network is involved—just the parser turning CLI strings into a namespace.

## What I didn’t cover / what could still break

- Port range (e.g. 0 or 99999) isn’t validated by argparse, so I didn’t test it; that’s more of a runtime concern.
- `--apps` accepts any string; validating things like "invalid_app" happens later in the command handler, not in the parser.
- I didn’t cover interaction between `--daemon`, `--pid`, `--stdout`, `--stderr`, and `--log-file` since that’s already in `test_api_server_command.py`.

## Follow-ups

- When new flags are added to `api-server`, we should add matching parser tests here.
- The existing `test_api_server_command.py` tests the full command with uvicorn/gunicorn mocks; these new tests only cover parsing so they stay fast and focused.
