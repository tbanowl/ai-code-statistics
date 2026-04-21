# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git AI is an open-source Rust CLI that tracks AI-generated code in git repositories. A single binary serves two roles based on `argv[0]`:
- **`git` (proxy mode)** — transparently wraps real git, injecting pre/post hooks per subcommand to track AI authorship
- **`git-ai` (direct mode)** — provides subcommands: checkpoint, blame, diff, status, stats, search, config, login, etc.

In debug builds, setting `GIT_AI=git` env var forces proxy mode regardless of binary name (used by integration tests).

## Build & Test Commands

```bash
# Build
cargo build                              # debug build
cargo build --release                    # release build
cargo build --features test-support      # debug build with git2 (for test binary)

# Test
cargo test                               # all tests (parallel)
cargo test --package git-ai --test <test_file_name> -- --nocapture  # single test file (FAST - skips building others)
cargo test <test_name>                   # single test by function name

# Lint & Format (CI uses Rust 1.93.0, RUSTFLAGS="-D warnings")
cargo clippy --all-targets -- -D warnings
cargo fmt -- --check
cargo fmt

# E2E tests (requires bats + debug build)
bats tests/e2e/user-scenarios.bats

# Snapshot management (insta crate)
cargo insta review                       # interactively review snapshot changes
cargo insta accept                       # accept all pending snapshots

# Coverage
cargo llvm-cov test --ignore-filename-regex='tests/.*|benches/.*|examples/.*'

# Dev setup (builds debug binary and installs to ~/.git-ai/bin/)
sh scripts/dev.sh                        # or: task dev
```

**Taskfile shortcuts**: `task build`, `task test`, `task lint`, `task format`, `task dev`, `task coverage`, `task test:e2e`

**Running specific commands with cargo**:
```bash
GIT_AI=git cargo run -- status           # run as git proxy
GIT_AI=git-ai cargo run -- checkpoint    # run as git-ai
```

**Nix dev environment**: `nix develop` provides pinned Rust 1.93.0 and wrapper scripts (`git`, `git-ai`, `git-og`) in `~/.git-ai-local-dev/gitwrap/bin/`. Use `git-og` to bypass the proxy.

## Architecture

### Module Structure (`src/lib.rs`)

| Module | Purpose |
|--------|---------|
| `commands/` | CLI dispatch: `git_handlers` (proxy), `git_ai_handlers` (direct), `hooks/` (per-subcommand pre/post hooks) |
| `authorship/` | Core attribution logic: working logs, post-commit note generation, rebase rewriting, attribution tracking |
| `commands/checkpoint_agent/` | Agent presets: parses hook input from each supported agent (Claude, Cursor, Copilot, Codex, etc.) |
| `daemon/` | Async mode: background process coordinates git operations via IPC (Unix sockets / Windows named pipes) |
| `git/` | Git operations: CLI parsing, repository discovery, refs, rewrite log, status, sync |
| `config/` | Global `OnceLock` singleton from `~/.git-ai/config.json`; feature flags from env vars (`GIT_AI_*` prefix) |
| `api/` | HTTP client for remote services (CAS, metrics, authorship notes, bundles) |
| `auth/` | OAuth device flow, credential storage, identity management |
| `metrics/` | Local SQLite metrics collection (events, stats) |
| `mdm/` | Machine/Device Management: agent detection, hook/skill installers, git client integration |
| `observability/` | Sentry/PostHog telemetry, performance tracing |
| `ci/` | CI environment detection (GitHub Actions, GitLab CI) |

### Core Data Flow

1. **Checkpoint** → Agent calls `git-ai checkpoint <agent>` with hook input (JSON stdin/env). Agent preset extracts edited paths and model info. Checkpoint processor diffs working tree against HEAD for character-level attributions.
2. **Working Log** → Stored in `.git/ai/working_logs/<base_commit>/` as JSON. Records per-file line attributions (AI vs human ranges) and prompt metadata.
3. **Post-commit** → Hook reads working logs, generates `AuthorshipLog` (schema `authorship/3.0.0`), stores as Git Note under `refs/notes/ai`.
4. **Rewrite tracking** → `.git/ai/rewrite_log` records history-rewriting ops. Post-hooks for rebase/cherry-pick/reset/merge/stash use `rebase_authorship.rs` to rewrite notes so attribution follows code through history.

### Git Proxy Hook Architecture (`src/commands/hooks/`)

Each git subcommand has dedicated pre/post hooks: `commit_hooks`, `rebase_hooks`, `cherry_pick_hooks`, `reset_hooks`, `stash_hooks`, `merge_hooks`, `checkout_hooks`, `switch_hooks`, `fetch_hooks`, `push_hooks`, `clone_hooks`, `plumbing_rewrite_hooks`, `update_ref_hooks`.

### Daemon (Async Mode)

When `async_mode` feature flag is enabled (default in release), git operations communicate with a background daemon via IPC. The daemon uses a Tokio runtime with actor-based coordination (`global_actor`, `family_actor`, `coordinator`).

## Test Infrastructure

### Integration Tests (`tests/integration/`)

~100 test modules in `tests/integration/main.rs`. Tests create real git repos using `git2` crate (behind `test-support` feature).

Key framework files in `tests/integration/repos/`:
- `test_repo.rs` — `TestRepo` struct: creates temp repos, runs git-ai as subprocess with `GIT_AI=git` env var
- `test_file.rs` — `TestFile` fluent API with `lines!` macro + `.ai()`/`.human()` for attribution expectations
- `mod.rs` — `subdir_test_variants!` macro auto-generates subdirectory and `-C` flag variants

```rust
#[test]
fn test_example() {
    let repo = TestRepo::new();
    let mut file = repo.filename("test.txt");
    file.set_contents(lines!["Line 1", "AI line".ai()]);
    repo.stage_all_and_commit("Initial commit").unwrap();
    file.assert_lines_and_blame(lines!["Line 1".human(), "AI line".ai()]);
}
```

### Test Isolation

- Each `TestRepo` gets a random temp dir and separate `GIT_AI_TEST_DB_PATH` (SQLite sibling to repo)
- `GIT_AI_TEST_CONFIG_PATCH` env var passes `ConfigPatch` JSON to override config in subprocess
- Background flush skipped when `GIT_AI_TEST_DB_PATH` is set
- Use `#[serial_test::serial]` for tests that conflict on shared env vars

## Key Conventions

- **Rust 2024 edition** with Rust 1.93.0 — uses let-chains (stable in edition 2024)
- **Git CLI over libgit2 in production** — all git operations use `std::process::Command`; `git2` is test-only
- **`debug_log()`** — prints `[git-ai]` to stderr when `cfg!(debug_assertions)` or `GIT_AI_DEBUG=1`
- **`GIT_AI_DEBUG_PERFORMANCE=1`** (or `=2` for JSON) enables timing output
- **POSIX-normalized paths** — `normalize_to_posix()` converts Windows backslashes; authorship logs always use `/`
- **Cross-platform** — 63 `#[cfg(windows)]` annotations across 17 files for signal handling, process creation, paths, terminal detection
- **Signal forwarding (Unix)** — git proxy installs handlers (SIGTERM, SIGINT, SIGHUP, SIGQUIT) that forward to child process group

## Feature Flags

Defined via `define_feature_flags!` macro in `src/feature_flags.rs`. Precedence: env vars (`GIT_AI_*`) > config file > defaults.

| Flag | Debug | Release | Purpose |
|------|-------|---------|---------|
| `rewrite_stash` | true | true | Preserve attribution across stash/pop |
| `inter_commit_move` | false | false | Track code moves between commits |
| `auth_keyring` | false | false | Use OS keyring for credentials |
| `async_mode` | false | true | Use daemon for git operations |
| `git_hooks_enabled` | false | false | Sunset: migrates to async_mode |
| `git_hooks_externally_managed` | false | false | Skip hook installation |

## Gotchas

- **argv[0] dispatch is load-bearing** — binary behavior determined entirely by invocation name. Breaking dispatch breaks everything.
- **Config is process-global** — `OnceLock` initialized once per process. Tests override via env var in subprocess, cannot change mid-process.
- **Feature flag debug/release divergence** — `async_mode` is false in debug, true in release. Tests run debug builds.
- **Large source files** — `rebase_authorship.rs` (~119K), `agent_presets.rs` (~101K), `repository.rs` (~96K), `attribution_tracker.rs` (~87K). Navigate with grep.
- **Git notes namespace** — Authorship data in `refs/notes/ai`. Use `git notes --ref=ai list` or `git log --notes=ai`.
- **Snapshot cascades** — Changing attribution logic can invalidate many snapshots. Use `cargo insta review`.
- **Test binary auto-compilation** — Integration tests trigger `cargo build --features test-support` via `OnceLock` on first run.
- **SQLite WAL files** — Test DB paths placed as siblings to repo dir (not inside `.git/`) to avoid git interference.
- **`smol` + `tokio` coexistence** — `smol` for lightweight async (HTTP, background flushes); `tokio` for daemon runtime.

## Pre-commit Hooks (lefthook)

Runs on `*.rs` and `*.toml` changes:
- `task format:check`
- `task lint`
- `task doc`
