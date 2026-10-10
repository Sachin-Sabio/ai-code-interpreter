# IITM TDS — AI Code Interpreter

FastAPI `POST /code-interpreter` accepts `{"code":"print(5 + 10)"}` and returns exactly `{"error":[],"result":"15\n"}`. CORS permits all origins. Python 3.11+.

On failure, `result` is the exact `traceback.format_exc()` string. Output printed before a failure is not prefixed to the traceback. On success only stdout is returned, preserving whitespace and newlines. Submitted source is compiled as `<submitted>` so line numbers are source-relative.

An LLM is called only after failure, with the original source and traceback. AIPipe's OpenAI-compatible endpoint is `https://aipipe.org/openrouter/v1`; set `AIPIPE_TOKEN` in the service environment. Never put the token in source control. Default model: `openai/gpt-4.1-nano`; override with `AIPIPE_MODEL`. Strict Pydantic JSON validation rejects malformed responses, strings, booleans, and extra fields. Line numbers must be in range and supported by the innermost submitted traceback frame. API/parse failures fall back to that frame.

## Isolation

Each request executes `exec()` in a fresh worker subprocess with an empty credential environment. Linux requires Landlock and libseccomp2: filesystem reads are limited to runtime library directories, writes are denied, and a syscall allowlist excludes network operations, process creation, exec, signals, and ptrace. Setup failure returns HTTP 503; it never silently runs without restrictions. macOS uses sandbox-exec with restricted file reads and denies network, writes, and process creation. No package installation or network access from submitted code.

Limits: 3 seconds wall time, 2 seconds CPU, 256 MiB virtual memory on Linux, 1 MB output/file size, 32 file descriptors, and 4 concurrent workers per server process. Excess concurrency returns 503. Source limit: 100,000 characters. Timeout/resource termination returns a diagnostic and no invented error line because there is no captured Python exception. Linux deployment needs a kernel with Landlock enabled. Render compatibility is not assumed: verify the deployed endpoint below before submission.

## Local development and tests

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
uvicorn main:app --host 0.0.0.0 --port 8000
```

On Linux install `libseccomp2` first. The Dockerfile uses Python 3.11, installs libseccomp2, and runs as an unprivileged user. CI tests Python 3.11 and 3.13 on Linux. macOS may require locally signing unsigned native Python dependency wheels if the OS refuses to load them.

## GitHub and Render deployment

1. Use the supplied repository `https://github.com/Sachin-Sabio/ai-code-interpreter`; authenticate GitHub CLI or the connector with write access. The connected sachin-a-iitm account currently has read-only access.
2. Publish the contents of this assignment directory as the repository root, excluding `.venv`, caches, and secrets. Include `.github/workflows/test.yml`; let CI finish before submitting.
3. In https://dashboard.render.com select **New → Blueprint**, connect the `Sachin-Sabio/ai-code-interpreter` repository, and use `render.yaml` on `main`.
4. Enter your AIPipe token for the prompted `AIPIPE_TOKEN` secret. The Blueprint selects a free Docker web service. Apply and wait for the deploy logs to finish.
5. Copy the actual service URL from Render. Verify execution, not just `/health`, because health does not exercise kernel sandbox support.
6. Run the live verification script below. A 503 means the sandbox failed: inspect service logs and use a Linux host supporting Landlock/seccomp rather than disabling isolation.
7. Submit only the actual verified URL with `/code-interpreter` appended.

```sh
python verify_live.py https://ACTUAL-SERVICE-HOST/code-interpreter
```

The script sends real POST requests for success and division by zero, checks both responses, and prints the verified submission URL only after both pass. AIPIPE_TOKEN is intentionally absent from this repository. No deployed URL is asserted until verification actually runs.
