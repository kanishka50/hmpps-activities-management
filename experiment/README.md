# Green DevOps measurement harness

Added to a fork of `ministryofjustice/hmpps-activities-management` (MIT, Crown
Copyright) for the research project *Towards Green DevOps: Measuring and
Optimising the Resource Consumption and Environmental Impact of CI/CD
Pipelines* (Kanishka, University of Kelaniya).

**The upstream application is not modified.** Everything added lives in
`experiment/`, `.github/workflows/pilot-config-*.yml`, `Dockerfile.experiment`
and `Dockerfile.experiment.dockerignore`. Each run verifies that `server/`,
`package.json` and `package-lock.json` still match upstream commit
`dc0f4b684ae02f3dcd6e8b73d1f3627cc7f81e80`, and fails if they do not.

## Files

| File | Purpose |
|---|---|
| `experiment/workflow-template.yml` | The single source for both pilot workflows |
| `experiment/generate-workflows.sh` | Generates Config A and Config B so they cannot drift |
| `experiment/run-pilot.sh` | Dispatches runs strictly serially in a seeded random order |
| `experiment/collect-results.sh` | Downloads artefacts and concatenates them into one CSV |
| `Dockerfile.experiment` | Deploy variant 1: package already-built artefacts |

## The pilot

Config A (uncached) and Config B (`cache: 'npm'`) differ in exactly one line.
Six stages are measured per run: install, lint, test, build, deploy-package,
deploy-image.

```bash
bash experiment/generate-workflows.sh    # after editing the template
bash experiment/run-pilot.sh 10 20260920 # 20 runs, serial, seeded
bash experiment/collect-results.sh       # download + combine
```

Nothing is published to npm, pushed to a registry, or sent to ECO-CI's servers
(`send-data: false` on every measurement).
