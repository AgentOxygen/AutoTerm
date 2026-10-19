# AutoTerm agent documentation

This directory documents the AutoTerm repository for LLM coding agents. Read this file first.

For the project's goal and the current task, read `CLAUDE.md` at the repository root. In short: the
immediate work is reproducing the original pipeline in a Docker container with minimal source
changes, so its output can serve as the accuracy reference and performance baseline for AutoTerm v2.
That goal changes how you should use this documentation. `pitfalls.md` in particular lists places
where the code contradicts the paper, and during reproduction those are behaviour to preserve, not
bugs to fix.

## What AutoTerm is, in three sentences

AutoTerm is a research pipeline that converts satellite images of Greenland outlet glaciers into
dated glacier terminus traces (line geometries marking the ice/ocean boundary). It was published as
Zhang, Catania, and Trugman (2023), The Cryosphere 17, 3485-3503, and produced 278,239 terminus
traces for 295 glaciers from 433,721 images spanning 1984 to 2021. The code in this repository is
the research code behind that paper: Bash driver scripts that call Python scripts, GDAL command
line tools, and GMT plotting commands.

## Read this before you change anything

1. The pipeline as committed to this repository cannot run end to end. Scripts are missing,
   absolute paths point at one machine that is not yours, and required data assets are not in git.
   See `pitfalls.md`.
2. There are two copies of the deep learning code: `pytorch-deeplab-xception/` at the repository
   root, and the `FrontDL3/` git submodule. They are not identical. Before editing either one, read
   `repository-map.md` to determine which copy is authoritative for your task.
3. `src/autoterm/` is a stub. It contains two files totalling four lines of code and no working
   functionality. Do not assume any packaged API exists. See `refactor-target.md`.
4. The paper and the code disagree in several specific places. The code is what runs. The paper is
   what the code was supposed to do. Both are listed in `pitfalls.md`.

## Which document to read for which task

| Your task | Read |
|---|---|
| Understand why a stage exists or what a number means | `science-context.md` |
| Trace data flow through the pipeline | `overview.md` |
| Find which file to edit, or resolve a duplicate file | `repository-map.md` |
| Learn what a specific directory or script does | `components.md` |
| Install, build, or run anything | `running-and-verifying.md` |
| Know what packages and CLI tools are required | `dependencies.md` |
| Parse or write pipeline data files | `conventions.md` |
| Avoid a known trap before writing code | `pitfalls.md` |
| Work on the packaging or refactor effort | `refactor-target.md` |

## Source documents outside this directory

| File | What it is | Status |
|---|---|---|
| `manuscript.md` (repository root) | The published paper, converted to Markdown | Authoritative for method intent and reported numbers |
| `AutoTerm Pipeline.docx` (repository root) | The author's step by step operating procedure | Authoritative for the intended manual setup sequence |
| `README.md` (repository root) | One line per directory | Accurate but minimal |
| `FrontDL3/README.md` | Upstream install instructions for the deep learning stage | Describes a Python 3.6 conda environment; outdated |
| `Dockerfile.frontdl3` (repository root) | A verified container build of the inference stage | Working. Read it before attempting any environment setup |

## Rules for agents working in this repository

1. Do not delete files that look like duplicates or backups. Several near-duplicate files carry
   real divergence and are imported by different entry points. `repository-map.md` lists them.
2. Do not "fix" a hardcoded path by substituting your own absolute path. Paths appear 76 times
   across 45 files. Changing them one at a time creates a second broken configuration. Treat path
   handling as a design task, not an edit.
3. When you change a number that appears in the paper (a threshold, a patch size, a learning rate),
   say so explicitly in your response. These values are published results.
4. Verify claims against the code, not against the paper or this documentation. This documentation
   was written by reading the code, but the code changes.
5. GPU is not required for inference if you use the `FrontDL3/` submodule. It is required if you
   use the root `pytorch-deeplab-xception/`. See `running-and-verifying.md`.
