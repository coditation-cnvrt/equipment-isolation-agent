# HILT SVG Viewer POC

A deliberately small, read-only POC that renders a real exported L2 HILT graph in an interactive SVG canvas. It uses the matching project-scoped CNVRT symbol library and preserves each node's original HILT payload for selection/property inspection.

## Run

```bash
cd hilt-viewer-poc
pnpm install
pnpm fetch-fixtures  # needs PLANT360_AUTH_TOKEN in ../.env
pnpm dev
```

Open the Vite URL and click **Load job 2100**.

## What it demonstrates

- Actual HILT exported graph: job `2100`
- Correct symbol library chosen from `hilt_graph.jobData.projectID` (`274` for that job), not an arbitrary project
- SVG P&ID primitives: HILT link segments, arrows, component SVGs, and associated text
- Pan (drag), zoom (mouse wheel), node selection, and a property panel containing the untouched original HILT node payload
- Fallback rectangles for an unmapped entity class

## Boundary of this POC

It adapts the exported L2 structure from `/jobs/get_job_hilt_graph/<jobId>`. It does not yet implement the different saved IM/CVT graph format returned by `/hilt/get_hilt/<jobId>`, nor every legacy symbol-flip/contour/text edge case. The fetched drawing and symbol JSON files are intentionally git-ignored.
