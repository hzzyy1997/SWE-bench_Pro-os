#!/usr/bin/env python3
"""
SWE-bench Pro harness using Claude Code (cc) as the coding agent.

Flow per instance:
  1. Pull Docker image for the instance
  2. Start container, copy /app repo to a local temp directory
  3. Reset to base_commit (clean state)
  4. Run `claude -p` with the problem_statement to let CC solve it
  5. Capture `git diff` as the patch
  6. Save all patches to a JSON file for evaluation

Usage:
  # Run a single instance (by index)
  python3 run_cc_harness.py --index 0

  # Run a range of instances
  python3 run_cc_harness.py --start 0 --end 5

  # Run a specific instance by ID
  python3 run_cc_harness.py --instance_id instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan

  # Then evaluate
  DOCKER_HOST=unix://$HOME/.colima/default/docker.sock python3 swe_bench_pro_eval.py \\
    --raw_sample_path=helper_code/sweap_eval_full_v2.jsonl \\
    --patch_path=cc_patches.json \\
    --output_dir=cc_eval_output/ \\
    --scripts_dir=run_scripts \\
    --use_local_docker --num_workers=1
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

from helper_code.image_uri import get_image_uri


def get_docker_host():
    if os.environ.get("DOCKER_HOST"):
        return os.environ["DOCKER_HOST"]
    sock = os.path.expanduser("~/.colima/default/docker.sock")
    if os.path.exists(sock):
        return f"unix://{sock}"
    return None


def docker_cmd(args, **kwargs):
    env = os.environ.copy()
    host = get_docker_host()
    if host:
        env["DOCKER_HOST"] = host
    return subprocess.run(
        ["docker"] + args,
        env=env,
        capture_output=True,
        text=True,
        **kwargs,
    )


def load_instances(data_path):
    instances = []
    with open(data_path) as f:
        for line in f:
            instances.append(json.loads(line))
    return instances


def run_instance(instance, output_dir, claude_model=None):
    """Run Claude Code on a single instance and return the patch."""
    iid = instance["instance_id"]
    repo = instance.get("repo", "")
    base_commit = instance["base_commit"]
    problem = instance["problem_statement"]
    image_uri = get_image_uri(iid, repo_name=repo)

    print(f"\n{'='*60}")
    print(f"Instance: {iid}")
    print(f"Image:    {image_uri}")
    print(f"{'='*60}")

    # Step 1: Pull image
    print("[1/5] Pulling image...")
    r = docker_cmd(["pull", image_uri, "--platform", "linux/amd64"], timeout=600)
    if r.returncode != 0:
        print(f"  Failed to pull image: {r.stderr}")
        return None

    # Step 2: Create container and copy /app to local temp dir
    print("[2/5] Copying repo from container...")
    workdir = os.path.join(output_dir, iid, "workdir")
    if os.path.exists(workdir):
        shutil.rmtree(workdir)
    os.makedirs(workdir, exist_ok=True)

    r = docker_cmd(["create", "--platform", "linux/amd64", image_uri, "true"])
    if r.returncode != 0:
        print(f"  Failed to create container: {r.stderr}")
        return None
    container_id = r.stdout.strip()

    try:
        r = docker_cmd(["cp", f"{container_id}:/app/.", workdir], timeout=120)
        if r.returncode != 0:
            print(f"  Failed to copy: {r.stderr}")
            return None
    finally:
        docker_cmd(["rm", container_id])

    # Step 3: Reset to base_commit
    print("[3/5] Resetting to base commit...")
    subprocess.run(
        ["git", "reset", "--hard", base_commit],
        cwd=workdir, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=workdir, capture_output=True, text=True,
    )

    # Step 4: Run Claude Code
    print("[4/5] Running Claude Code...")
    prompt = f"""You are solving a software engineering task. Here is the problem:

{problem}

Please fix the code to resolve this issue. Only modify the necessary files.
Do not add tests. Do not modify test files.
"""

    claude_args = ["claude", "-p", prompt, "--max-turns", "20"]
    if claude_model:
        claude_args.extend(["--model", claude_model])

    r = subprocess.run(
        claude_args,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=600,
    )

    if r.returncode != 0:
        print(f"  Claude Code failed (exit {r.returncode})")
        if r.stderr:
            print(f"  stderr: {r.stderr[:500]}")

    # Step 5: Capture git diff
    print("[5/5] Capturing patch...")
    r = subprocess.run(
        ["git", "diff"],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    patch = r.stdout.strip()

    if not patch:
        # Also check for untracked files
        r2 = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=workdir, capture_output=True, text=True,
        )
        patch = r2.stdout.strip()

    if patch:
        print(f"  Patch captured ({len(patch)} chars)")
        # Save patch to file for reference
        patch_file = os.path.join(output_dir, iid, "cc_patch.diff")
        with open(patch_file, "w") as f:
            f.write(patch)
    else:
        print("  No changes detected")

    return patch


def parse_args():
    parser = argparse.ArgumentParser(description="Run Claude Code on SWE-bench Pro instances")
    parser.add_argument(
        "--data_path", default="helper_code/sweap_eval_full_v2.jsonl",
        help="Path to the JSONL data file",
    )
    parser.add_argument(
        "--output_dir", default="cc_output",
        help="Directory for working files and patches",
    )
    parser.add_argument(
        "--patches_json", default="cc_patches.json",
        help="Output JSON file with all patches",
    )
    parser.add_argument("--index", type=int, default=None, help="Run a single instance by index")
    parser.add_argument("--start", type=int, default=None, help="Start index (inclusive)")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive)")
    parser.add_argument("--instance_id", default=None, help="Run a specific instance by ID")
    parser.add_argument("--model", default=None, help="Claude model to use (e.g. sonnet, opus)")
    return parser.parse_args()


def main():
    args = parse_args()
    instances = load_instances(args.data_path)
    print(f"Loaded {len(instances)} instances")

    # Select instances to run
    if args.instance_id:
        selected = [i for i in instances if i["instance_id"] == args.instance_id]
        if not selected:
            print(f"Instance {args.instance_id} not found")
            sys.exit(1)
    elif args.index is not None:
        selected = [instances[args.index]]
    elif args.start is not None:
        end = args.end or (args.start + 1)
        selected = instances[args.start:end]
    else:
        selected = instances

    print(f"Running {len(selected)} instance(s)")
    os.makedirs(args.output_dir, exist_ok=True)

    # Load existing patches if any
    all_patches = []
    if os.path.exists(args.patches_json):
        with open(args.patches_json) as f:
            all_patches = json.load(f)

    existing_ids = {p["instance_id"] for p in all_patches}

    for inst in selected:
        iid = inst["instance_id"]
        if iid in existing_ids:
            print(f"\nSkipping {iid} (patch already exists)")
            continue

        patch = run_instance(inst, args.output_dir, claude_model=args.model)

        all_patches.append({
            "instance_id": iid,
            "model_patch": patch or "",
            "prefix": "cc",
        })

        # Save after each instance
        with open(args.patches_json, "w") as f:
            json.dump(all_patches, f, indent=2)
        print(f"Saved {len(all_patches)} patches to {args.patches_json}")

    print(f"\nDone. Total patches: {len(all_patches)}")
    print(f"Patches file: {args.patches_json}")
    print(f"\nTo evaluate:")
    print(f"  DOCKER_HOST=unix://$HOME/.colima/default/docker.sock python3 swe_bench_pro_eval.py \\")
    print(f"    --raw_sample_path={args.data_path} \\")
    print(f"    --patch_path={args.patches_json} \\")
    print(f"    --output_dir=cc_eval_output/ \\")
    print(f"    --scripts_dir=run_scripts \\")
    print(f"    --use_local_docker --num_workers=1")


if __name__ == "__main__":
    main()
