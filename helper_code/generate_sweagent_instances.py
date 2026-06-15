#!/usr/bin/env python3
"""
Generate SWE-agent instance YAML file from HuggingFace SWE-bench Pro dataset.

This script loads the SWE-bench Pro dataset and generates a YAML file containing
all instances formatted for use with SWE-agent. Each instance includes the Docker
image name, problem statement, instance ID, base commit, and repo name.

Usage:
    python generate_sweagent_instances.py
    python generate_sweagent_instances.py --image_registry <registry-prefix> --output_path custom_instances.yaml
"""

import argparse
import os
import yaml
from tqdm import tqdm
from datasets import load_dataset

# Import helper functions from the same directory
from image_uri import get_image_uri, DEFAULT_REGISTRY
from create_problem_statement import create_problem_statement


def generate_instances(registry_prefix=DEFAULT_REGISTRY, dataset_split='test'):
    """
    Load SWE-bench Pro dataset and generate instance list.

    Args:
        registry_prefix: Registry prefix for image URI generation
        dataset_split: Which split of the dataset to use (default: 'test')

    Returns:
        list: List of instance dictionaries formatted for YAML output
    """
    print(f"Loading SWE-bench Pro dataset (split: {dataset_split})...")
    swebench_pro = load_dataset('ScaleAI/SWE-bench_Pro', split=dataset_split)

    instances = []
    print(f"Processing {len(swebench_pro)} instances...")

    for row in tqdm(swebench_pro):
        instance_id = row['instance_id']
        repo_name = row.get('repo', '')
        image_name = get_image_uri(instance_id, registry_prefix, repo_name)
        
        # Create formatted problem statement
        problem_statement = create_problem_statement(row)
        
        # Create instance dictionary matching the format of example_instances.yaml
        instance = {
            'image_name': image_name,
            'problem_statement': problem_statement,
            'instance_id': instance_id,
            'base_commit': row['base_commit'],
            'repo_name': 'app'  # Hardcoded as specified
        }
        
        instances.append(instance)
    
    return instances


def write_yaml(instances, output_path):
    """
    Write instances to YAML file.
    
    Args:
        instances: List of instance dictionaries
        output_path: Path to output YAML file
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Writing {len(instances)} instances to {output_path}...")
    with open(output_path, 'w') as f:
        yaml.dump(instances, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print(f"✓ Successfully generated {output_path}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate SWE-agent instances from HuggingFace SWE-bench Pro dataset',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate instances with default registry
  python generate_sweagent_instances.py

  # Generate instances with custom registry and output path
  python generate_sweagent_instances.py --image_registry myregistry/myns --output_path custom_instances.yaml

  # Use a different dataset split
  python generate_sweagent_instances.py --dataset_split dev
        """
    )
    
    parser.add_argument(
        '--image_registry',
        default=DEFAULT_REGISTRY,
        help=f'Registry prefix for generating image URIs (default: {DEFAULT_REGISTRY})'
    )
    
    parser.add_argument(
        '--output_path',
        default='SWE-agent/data/instances.yaml',
        help='Output path for the generated YAML file (default: SWE-agent/data/instances.yaml)'
    )
    
    parser.add_argument(
        '--dataset_split',
        default='test',
        help='Which split of the dataset to use (default: test)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Generate instances
    instances = generate_instances(args.image_registry, args.dataset_split)
    
    # Write to YAML file
    write_yaml(instances, args.output_path)
    
    print(f"\n✓ Done! Generated {len(instances)} instances.")
    print(f"  Output: {args.output_path}")
    print(f"\nYou can now use this file with SWE-agent:")
    print(f"  --instances.type file \\")
    print(f"  --instances.path {args.output_path}")


if __name__ == "__main__":
    main()

