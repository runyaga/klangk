#!/usr/bin/env python3
"""Fetch external plugins declared in plugins/plugins.yaml.

If plugins/ doesn't exist, creates it with a template plugins.yaml.
If plugins/plugins.yaml exists, fetches listed plugins and writes plugins.lock.
"""

import os
import shutil
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS_DIR = os.path.join(ROOT, "plugins")
YAML_PATH = os.path.join(PLUGINS_DIR, "plugins.yaml")
LOCK_PATH = os.path.join(PLUGINS_DIR, "plugins.lock")

DEFAULT_TEMPLATE = """\
# Bark plugins configuration
# Run 'update-plugins' to fetch plugins listed here.
plugins:
  # Default plugins (from the Bark repo)
  - git: git@github.com:mcdonc/bark.git
    path: default-plugins/celebrate
    ref: main
  - git: git@github.com:mcdonc/bark.git
    path: default-plugins/beep
    ref: main
  - git: git@github.com:mcdonc/bark.git
    path: default-plugins/pig-latin
    ref: main
  - git: git@github.com:mcdonc/bark.git
    path: default-plugins/word-count
    ref: main
  # Add more plugins below:
  # - git: git@github.com:mcdonc/bark.git-plugins
  #   path: soliplex
  #   ref: v1.0.0
"""


def resolve_ref(git_url, ref):
    """Resolve a git ref (branch, tag, or SHA) to a commit SHA."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", git_url, ref],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.strip().splitlines():
            sha, _name = line.split("\t", 1)
            return sha
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # If ls-remote didn't match, assume ref is already a SHA
    return ref


def fetch_plugin(plugin, plugins_dir):
    """Fetch a single plugin from a git repo into plugins_dir."""
    git_url = plugin["git"]
    ref = plugin.get("ref", "main")
    subpath = plugin.get("path", "")

    # Determine plugin name from path or repo name
    if subpath:
        name = os.path.basename(subpath)
    else:
        name = os.path.basename(git_url.rstrip("/"))
        if name.endswith(".git"):
            name = name[:-4]

    dest = os.path.join(plugins_dir, name)

    # Resolve ref to SHA
    sha = resolve_ref(git_url, ref)
    if not sha:
        print(f"  ERROR: Could not resolve ref '{ref}' for {git_url}", file=sys.stderr)
        return None

    print(f"  {name}: {git_url} @ {ref} -> {sha[:12]}")

    # Clone into temp dir, then copy the subpath
    with tempfile.TemporaryDirectory() as tmpdir:
        clone_dir = os.path.join(tmpdir, "repo")
        result = subprocess.run(
            ["git", "clone", "--depth=1", "--branch", ref, git_url, clone_dir],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            # ref might be a SHA, try full clone
            result = subprocess.run(
                ["git", "clone", git_url, clone_dir],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                print(f"  ERROR: git clone failed: {result.stderr.strip()}",
                      file=sys.stderr)
                return None
            subprocess.run(
                ["git", "checkout", ref],
                cwd=clone_dir, capture_output=True, text=True,
            )

        source = os.path.join(clone_dir, subpath) if subpath else clone_dir

        if not os.path.isdir(source):
            print(f"  ERROR: path '{subpath}' not found in {git_url}",
                  file=sys.stderr)
            return None

        # Remove old version and copy
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

        # Remove .git if it was copied
        git_dir = os.path.join(dest, ".git")
        if os.path.exists(git_dir):
            shutil.rmtree(git_dir)

    return {"name": name, "git": git_url, "path": subpath, "ref": ref, "sha": sha}


def write_lock(entries, lock_path):
    """Write the lockfile."""
    with open(lock_path, "w") as f:
        yaml.dump({"plugins": entries}, f, default_flow_style=False, sort_keys=False)


def main():
    # Create plugins/ with template if it doesn't exist
    if not os.path.exists(YAML_PATH):
        os.makedirs(PLUGINS_DIR, exist_ok=True)
        with open(YAML_PATH, "w") as f:
            f.write(DEFAULT_TEMPLATE)
        print(f"Created template {YAML_PATH}")
        print("Edit it to add plugins, then run 'update-plugins' again.")
        return

    # Read plugins.yaml
    with open(YAML_PATH) as f:
        config = yaml.safe_load(f)

    plugins = config.get("plugins", [])
    if not plugins:
        print("No plugins listed in plugins.yaml")
        return

    print(f"Fetching {len(plugins)} plugins...")

    lock_entries = []
    for plugin in plugins:
        if "git" not in plugin:
            print(f"  SKIP: entry missing 'git' key: {plugin}", file=sys.stderr)
            continue
        entry = fetch_plugin(plugin, PLUGINS_DIR)
        if entry:
            lock_entries.append(entry)

    write_lock(lock_entries, LOCK_PATH)
    print(f"Wrote {LOCK_PATH} with {len(lock_entries)} plugins")


if __name__ == "__main__":
    main()
