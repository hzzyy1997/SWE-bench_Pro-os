"""
Utilities for generating Docker image URIs for SWE-bench Pro instances.

This module provides functions to convert instance IDs and repository names
into properly formatted image URIs that match the expected format
from the upload scripts.
"""

DEFAULT_REGISTRY = "devops-registry.cn-hangzhou.cr.aliyuncs.com/long-range"


def get_image_uri(uid, registry_prefix=DEFAULT_REGISTRY, repo_name=""):
    repo_base, repo_name_only = repo_name.lower().split("/")
    hsh = uid.replace("instance_", "")

    if uid == "instance_element-hq__element-web-ec0f940ef0e8e3b61078f145f34dc40d1938e6c5-vnan":
        repo_name_only = 'element-web'
    elif 'element-hq' in repo_name.lower() and 'element-web' in repo_name.lower():
        repo_name_only = 'element'
        if hsh.endswith('-vnan'):
            hsh = hsh[:-5]
    elif hsh.endswith('-vnan'):
        hsh = hsh[:-5]

    tag = f"{repo_base}.{repo_name_only}-{hsh}"
    if len(tag) > 128:
        tag = tag[:128]

    return f"{registry_prefix}/sweap-images:{tag}"

