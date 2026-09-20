#!/usr/bin/env python3
"""Generate the five pipeline-configuration workflows from the templates.

The point of generating them is that the configurations then CANNOT differ in
anything except the factors that define them. Editing a generated workflow by
hand defeats that guarantee - edit the template instead and re-run this.

    python experiment/generate-workflows.py

Configurations (the independent variable, at five levels):

    A Full             no cache | lint | all tests
    B Cached           CACHE    | lint | all tests
    C Minimal          no cache | ---- | 1/4 of tests
    D Cached+Minimal   CACHE    | ---- | 1/4 of tests
    E Cached+Parallel  CACHE    | lint and test as parallel jobs (3 VMs)
    F Cached+Workers   CACHE    | lint | all tests, ACROSS THE RUNNER'S CORES

"Minimal" is mechanical: lint removed, tests run with the runner's own
`--shard=1/4`. Nothing is selected by hand, so no subset can have been chosen
for its effect.

Configurations E and F are two different meanings of "run the tests in
parallel", and separating them is the point of F:

    E spreads the work over THREE MACHINES. Each is a fresh VM that installs
      its own dependencies, so the install stage is paid three times.
    F spreads the work over the CORES OF ONE MACHINE. Nothing is duplicated;
      the runner already has four cores and the subject uses one of them.

B is the common control for both: B, E and F run identical work (cache, lint,
the whole suite) and differ only in how the test stage is distributed.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = ROOT / "experiment" / "templates"
OUT = ROOT / ".github" / "workflows"

NO_CACHE = "          # NO `cache:` key. This is an UNCACHED configuration."
CACHE = "          # Dependency caching ON - a defining factor of this configuration.\n          cache: 'npm'"

TEST_ALL = "npx jest --runInBand"
# The subject's own package.json pins `--runInBand`, which runs the whole suite
# in ONE process. Configurations A-E inherit that faithfully. Config F removes
# it and nothing else, so Jest falls back to ITS OWN default worker count
# (cores - 1; the runner logs `nproc`, so the worker count is recoverable for
# every run). The count is the runner's decision, not ours, for the same reason
# `--shard=1/4` is: a number chosen by hand could be suspected of being chosen
# for its effect.
TEST_WORKERS = "npx jest"
# --shard=1/4 is Jest's own deterministic quarter of the suite: the same files
# every run, chosen by the runner rather than by us.
TEST_SHARD = "npx jest --runInBand --shard=1/4"

LINT_BLOCK = """
      # ================= STAGE: LINT =================
      - name: Lint
        run: npm run lint

      - name: ECO-CI - measure lint
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: lint
          send-data: false
"""

# Config C and D remove the lint stage entirely; the comment keeps the removal
# visible in the generated file rather than leaving a silent gap.
NO_LINT_BLOCK = """
      # ================= STAGE: LINT - REMOVED =================
      # This is a MINIMAL configuration: the lint stage is not run. Lint emits
      # no files (eslint reports; tsc runs with --noEmit), so no later stage
      # loses an input. What is given up is detection, not build correctness.
"""

SINGLE = [
    # id, name, cache line, lint block, test command, expected measurement rows
    ("A", "Full", NO_CACHE, LINT_BLOCK, TEST_ALL, 5),
    ("B", "Cached", CACHE, LINT_BLOCK, TEST_ALL, 5),
    ("C", "Minimal", NO_CACHE, NO_LINT_BLOCK, TEST_SHARD, 4),
    ("D", "Cached+Minimal", CACHE, NO_LINT_BLOCK, TEST_SHARD, 4),
    ("F", "Cached+Workers", CACHE, LINT_BLOCK, TEST_WORKERS, 5),
]

# Config E: three jobs. lint and test run concurrently; build+deploy waits for
# both. Each job installs for itself because each is a fresh VM.
PARALLEL_JOBS = [
    (
        "lint",
        "Lint (parallel with test)",
        "",
        """      - name: Lint
        run: npm run lint

      - name: ECO-CI - measure lint
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: lint
          send-data: false
""",
        2,
    ),
    (
        "test",
        "Test (parallel with lint)",
        "",
        """      - name: Test
        env:
          NODE_ENV: unit-test
          TZ: utc
          NODE_OPTIONS: '--max_old_space_size=4096 --experimental-vm-modules'
        run: npx jest --runInBand

      - name: ECO-CI - measure test
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: test
          send-data: false
""",
        2,
    ),
    (
        "build",
        "Build and deploy",
        "    needs: [lint, test]",
        """      - name: Build
        run: npm run build

      - name: ECO-CI - measure build
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: build
          send-data: false

      - name: Deploy (package built app into image)
        run: docker build -f Dockerfile.experiment -t hmpps-activities:packaged .

      - name: ECO-CI - measure deploy
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: deploy
          send-data: false
""",
        3,
    ),
]

HEADER = "# GENERATED FILE - do not edit. Regenerate with:\n#   python experiment/generate-workflows.py\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    single_tpl = (TPL / "single-job.yml").read_text(encoding="utf-8")

    for cid, name, cache, lint, test_cmd, rows in SINGLE:
        text = (
            single_tpl.replace("@@CONFIG@@", cid)
            .replace("@@CONFIG_NAME@@", name)
            .replace("@@CACHE_LINE@@", cache)
            .replace("@@LINT_BLOCK@@", lint)
            .replace("@@TEST_CMD@@", test_cmd)
            .replace("@@EXPECTED_ROWS@@", str(rows))
        )
        path = OUT / f"config-{cid.lower()}.yml"
        path.write_text(HEADER + text, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")

    head = (TPL / "parallel-header.yml").read_text(encoding="utf-8")
    job_tpl = (TPL / "parallel-job.yml").read_text(encoding="utf-8")
    parts = [head]
    for job_id, job_name, needs, work, rows in PARALLEL_JOBS:
        parts.append(
            job_tpl.replace("@@JOB_ID@@", job_id)
            .replace("@@JOB_NAME@@", job_name)
            .replace("@@NEEDS@@", needs)
            .replace("@@WORK@@", work)
            .replace("@@EXPECTED_ROWS@@", str(rows))
        )
    path = OUT / "config-e.yml"
    path.write_text(HEADER + "\n".join(parts), encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
