# Run SWE-bench Pro: Generate Patch with Claude Code + Evaluate

This skill runs the full SWE-bench Pro pipeline: use Claude Code as the coding agent to solve an instance, then evaluate the patch in Docker.

## Arguments

- `$ARGUMENTS` — instance index (e.g. `0`), instance ID (e.g. `instance_NodeBB__NodeBB-xxx`), or a range (e.g. `0-5`). Defaults to index `0` if omitted.

## Steps

### 1. Parse arguments

Determine which instance(s) to run from `$ARGUMENTS`:
- If it looks like an `instance_*` ID, use `--instance_id`
- If it contains `-`, treat as a range (`--start X --end Y`)
- Otherwise treat as a single index (`--index N`)

### 2. Generate patches

Run the harness script to generate patches using Claude Code:

```bash
python3 run_cc_harness.py <parsed_args> --output_dir cc_output --patches_json cc_patches.json
```

This will:
1. Pull the Docker image for the instance
2. Copy the repo code from the container to a local working directory
3. Reset to the base commit
4. Run `claude -p` with the problem statement to solve it
5. Capture `git diff` as the patch
6. Save to `cc_patches.json`

### 3. Evaluate patches

After patch generation completes, run the evaluation:

```bash
DOCKER_HOST=unix://$HOME/.colima/default/docker.sock python3 swe_bench_pro_eval.py \
  --raw_sample_path=helper_code/sweap_eval_full_v2.jsonl \
  --patch_path=cc_patches.json \
  --output_dir=cc_eval_output/ \
  --scripts_dir=run_scripts \
  --use_local_docker \
  --num_workers=1 \
  --redo
```

### 4. Report results

Read and report the evaluation results from `cc_eval_output/eval_results.json`. Show:
- Which instances passed / failed
- Overall accuracy
