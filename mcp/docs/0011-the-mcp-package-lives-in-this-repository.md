# 0011: The MCP package lives in this repository

Status: accepted
Date: 2026-08-26
Relates to: [0008](0008-the-mcp-server-runs-inside-precogly.md)
Supersedes: the submodule in [0008](0008-the-mcp-server-runs-inside-precogly.md)'s Deferred section

`precogly-mcp` is a uv workspace member of `precogly/precogly`, at `mcp/`. The backend
depends on it by source rather than by version, and `precogly/precogly-mcp` is archived
with a pointer here.

## Context

[0008](0008-the-mcp-server-runs-inside-precogly.md) put the MCP endpoint inside Precogly's
own WSGI process and left "submoduling this repository into precogly/precogly" as the
intended end state. Two things had to happen for that to be an end state at all, and both
now have: the code is written and its tests pass, and the Django half that mounts it is on
a branch of this repository rather than in a working copy.

Until then the two halves were joined by a Docker mount. `docker-compose.yml` mounted
`../precogly-mcp` at `/precogly-mcp` and the dev image's CMD ran `pip install -e` on it at
container start, because an unreleased package cannot be a line in the dependency list and
the working copy does not exist while the image is being built. That works only for
someone who has both repositories checked out as siblings, which is a setup step nothing
states and CI cannot have.

## Decision

**One workspace, one lock.** The repository root carries a virtual `pyproject.toml` whose
only content is `[tool.uv.workspace] members = ["backend", "mcp"]`. `uv.lock` moves from
`backend/` to the root, because uv keeps one lock per workspace. `backend/pyproject.toml`
gains `precogly-mcp` as a dependency and `precogly-mcp = { workspace = true }` as its
source, so it resolves from `../mcp` and never from an index.

**No submodule.** A submodule keeps the second repository, which is the thing being
removed: a contributor still clones twice, CI still checks out twice, and a change
spanning both halves is still two pull requests that cannot be merged atomically. The
mount above is the same coupling with worse ergonomics. Nothing in the git history is lost
by archiving instead — `precogly/precogly-mcp` stays public and readable, so a permalink
into it keeps resolving.

**The backend image builds from the repository root.** The lock and the `mcp` member both
sit above `backend/`, so `context: ./backend` can no longer reach them.
`docker-compose.yml` sets `context: .` and `dockerfile: backend/Dockerfile`, the Dockerfile
copies `backend/` and `mcp/` explicitly rather than `.`, and a root `.dockerignore` keeps
`frontend/node_modules` out of what is sent to the daemon.

**`--no-install-workspace`, not `--no-install-project`, for the dependency-only layer.**
The distinction is invisible until it fails: with no root project to skip,
`--no-install-project` goes ahead and installs `precogly-mcp` from a directory that layer
has not copied yet. Measured on this workspace, the two differ by exactly that one package
— 112 installed against 111.

**Nothing installs at container start.** uv installs workspace members editable, as a
`.pth` pointing at `/app/mcp`, so the compose mount over that path is live in the same way
the old `pip install -e` was. The dev CMD goes back to `migrate && seed && runserver`.

## Rejected

- **Folding the package into `backend/` as an ordinary module.** No second manifest, no
  workspace, one COPY line in the Dockerfile, and none of the build-context move above.
  Rejected because it dissolves the seam [0008](0008-the-mcp-server-runs-inside-precogly.md)
  draws: the tools read Precogly through a protocol this package defines and the mounting
  application implements, and a module inside the Django project can import Django by
  accident and stop being checkable. The seam is what keeps stdio working and what makes
  the tests runnable without a database. The cost is real and lands on files unrelated to
  MCP, which is the strongest argument for the other answer.

- **A path dependency without a workspace** (`{ path = "../mcp", editable = true }`).
  Reaches the same code with no root manifest, but leaves two locks that resolve
  independently and can disagree about a shared dependency — the failure the uv migration
  removed from `requirements/`.

- **Publishing to PyPI and depending by version.** It reinstates the release-coordination
  problem [0008](0008-the-mcp-server-runs-inside-precogly.md) removed: the server ships on
  Precogly's release train, so a fix would need a release of this package before Precogly
  could take it.

## Trade-offs

- **The Docker build context is the whole repository.** Every backend build now sends the
  root through to the daemon, and `.dockerignore` is what keeps that cheap. Adding a large
  directory at the top level without an entry there quietly slows every build.

- **Dependabot's uv directory moved to `/`.** It follows the lock, and a config still
  pointing at `/backend` would find a manifest with no lock beside it and update nothing —
  silently, since nothing fails when no PR is opened.

- **The two members' shared tool ranges are written identically by hand.** One resolution
  covers the workspace, so `backend/pyproject.toml` and `mcp/pyproject.toml` cannot
  actually disagree about ruff or mypy; a wider range on one side is not a second version,
  only a misleading one. Nothing enforces that they match.

- **`mcp/` reads as a peer of `backend/` and `frontend/`, which overstates it.** It is
  deployed only inside the backend process. The layout is chosen for where a reader looks
  first, not for the deployment topology.

## Deferred

- **`pip-audit` in CI.** It came across in the dev group and the archived repository ran it
  on every push; nothing here does yet. It belongs with the rest of the dependency-scanning
  work rather than bolted onto this move.

- **A `uv-lock` pre-commit hook.** The archived repository had one, catching a manifest
  edited without re-locking. The root hooks do not, and the failure it prevents is now
  repository-wide rather than confined to this package.
