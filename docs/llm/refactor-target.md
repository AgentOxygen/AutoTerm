# Refactor target

The intended direction of travel. Nothing in this document describes working code.

## Current state of `src/autoterm/`

The package is a stub. It contains two files and four lines of code in total.

| File | Contents |
|---|---|
| `src/autoterm/autoterm.py` | The single line `import pytorch` |
| `src/autoterm/cli.py` | A `main()` function with a `pass` body, and a `__main__` guard |

There is no `__init__.py`.

Do not assume any packaged API exists. Nothing in the legacy pipeline imports from `autoterm`, and
`autoterm` imports nothing from the legacy pipeline.

## Known defects in the current scaffolding

These are facts about the committed files, not opinions about design.

1. `src/autoterm/autoterm.py` contains `import pytorch`. The PyTorch import name is `torch`. There
   is no module named `pytorch` on PyPI that this would resolve to.
2. `pyproject.toml` sets `[tool.setuptools] packages = ["autoterm"]` with no `package-dir` entry.
   The code lives under `src/`, so setuptools will look for `./autoterm` and not find it. Either
   `[tool.setuptools.packages.find] where = ["src"]` or an explicit `package-dir` mapping is needed.
3. `pyproject.toml` declares `dev = ["AutoTerm[test,docs,sphinx,sphinx-autobuild]"]`. None of the
   four referenced extras, `test`, `docs`, `sphinx`, or `sphinx-autobuild`, are defined in
   `[project.optional-dependencies]`. Installing the `dev` extra will fail to resolve.
4. `[project] dependencies` is an empty list. The real dependency set is large and is documented in
   `dependencies.md`.
5. `[project.scripts]` declares `autoterm_cli = "autoterm.cli:main"`, and `main()` does nothing.

## Where this fits in the project plan

The project has two phases, stated in `CLAUDE.md` at the repository root.

Phase 1 is reproducing the original pipeline in a Docker container with as few source changes as
possible. Phase 2, which is what this document describes, is building AutoTerm v2 against the
reproduction's output as an accuracy reference and performance baseline.

**Phase 1 is the current work. Do not begin the refactor described here until an end-to-end
reproduction produces output.** Without a reference output, there is nothing to verify a v2 port
against, and the main safeguard against silently changing published results is gone.

## What the target appears to be

The two-phase goal above is confirmed. The specific structure below is inferred from the branch name
`1-create-dev-environment-and-toolkit-structure` and the `pyproject.toml` contents, and is not a
written specification. Confirm before making large structural decisions.

The goal is to turn research code into an installable, reproducible toolkit:

1. A real Python package under `src/autoterm/`, installable with `pip install .`.
2. A command line entry point, `autoterm_cli`, replacing the current set of Bash drivers.
3. A declared dependency set, replacing the current situation where dependencies are discovered by
   reading imports.
4. A reproducible container, replacing the manual conda and `PATH` setup in the operating procedure.
5. Documentation built with Sphinx, implied by the `docs`, `sphinx`, and `sphinx-autobuild` extras
   named in `pyproject.toml`.
6. Configuration that does not require absolute paths to one machine.

## Problems any refactor has to solve

These are the structural obstacles, in rough order of how much they constrain the design.

### Path resolution

76 hardcoded absolute paths across 45 files, none resolved relative to the script. This is the
single largest blocker. Any packaging effort has to replace them with something, and the
replacement has to serve both the Python and the Bash halves of the pipeline, because the Bash
scripts read configuration by shelling out to `parameters.py`.

### The Bash and Python boundary

The pipeline's control flow is in Bash and its computation is in Python. The Bash layer does the
per-glacier looping, the file discovery, the directory creation, and the calls to GDAL and GMT
command line tools. Porting only the Python half produces a package that cannot run the pipeline.

Decide explicitly whether the target keeps Bash orchestration, replaces it with Python, or wraps it.

### External command line tools

GDAL and GMT are invoked as subprocesses, not through libraries, in almost every stage. A pip
installable package cannot install the GDAL command line tools or GMT. The container is the only
place where that dependency can be satisfied cleanly.

### Configuration format

`para.ini` is plain `key = value` text parsed by a 2016 script, read one key at a time by shelling
out to that script. Both the global and per-glacier files use it. Replacing it means changing both
the Python readers and every Bash call site.

### Missing stages

The paper describes five features with no code in this repository at all: TermPicks label
generation, flowline intersection screening, ice and ocean mask generation, automatic region of
interest update, and glacier ID maintenance. A toolkit that claims to implement AutoTerm has to
either implement these or state that it does not.

### Which copy of the network code wins

Two copies exist, described in `repository-map.md`. The submodule fork runs on modern Python and on
CPU; the root copy does not. A refactor has to pick one, and the submodule is the better starting
point on technical grounds.

## Guidance for agents working on the refactor

1. Do not delete legacy directories. They are the reference implementation and the only
   documentation of what the pipeline actually does.
2. Do not port a script without reading its call sites. Argument order is positional and
   undocumented in most `batch_*.sh` scripts.
3. Preserve every published numeric value unless asked to change it. Thresholds, patch sizes, and
   the 0.5 binarization cutoff are results, not implementation details.
4. Prefer adding new code under `src/autoterm/` over editing legacy scripts in place, so the
   reference behaviour stays available for comparison.
5. When you port a stage, verify it against the legacy output rather than against this
   documentation.
