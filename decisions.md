# Decisions — IITM TDS AI Code Interpreter

- 2026-10-11: Reuse starter zip, in a separate assignment directory. Existing Sabio work and remote are unrelated and must not be published for this assignment.
- 2026-10-11: Target GitHub owner sachin-a-iitm per explicit user correction.
- 2026-10-11: Use a fresh subprocess per request with sanitized environment, wall/CPU limits, output and memory bounds. Linux uses Landlock filesystem confinement and default-deny seccomp; macOS uses sandbox-exec. Sandbox setup failure refuses execution. A subprocess alone does not isolate filesystem or network access.
- 2026-10-11: Success returns stdout exactly; failures return traceback.format_exc() exactly, without prefixing previous output. Timeout/resource termination has no Python traceback and returns a diagnostic with no fabricated line numbers.
- 2026-10-11: Use openai/gpt-4.1-nano, documented by AIPipe and currently listed by OpenRouter at $0.10/M input and $0.40/M output. Override with AIPIPE_MODEL.
- 2026-10-11: Strict Pydantic validation plus innermost submitted traceback evidence prevents out-of-range and unsupported line guesses. Malformed/API failures fall back to actual traceback evidence.
- 2026-10-11: Deploy a non-root Docker service to install libseccomp reliably. Linux sandbox compatibility must be verified on the deployed Render kernel before claiming deployment success.
- 2026-10-11: User supplied Sachin-Sabio/ai-code-interpreter as the repository URL, superseding the earlier owner choice. Connected sachin-a-iitm account has pull=true, push=false; publishing awaits write authentication or a repository under the connected owner.
- 2026-10-11: Bound OS-level stdout/stderr writes with file size limits as well as Python stdout capture limits, to prevent low-level writes exhausting server memory.
- 2026-10-11: Local pytest is blocked during collection by macOS native extension mmap denial, on both Python 3.14 and 3.13. Do not claim application tests passed. Preserve actual results and require Linux CI plus live execution verification.
