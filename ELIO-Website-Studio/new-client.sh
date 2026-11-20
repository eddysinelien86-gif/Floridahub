#!/usr/bin/env bash
# Create a new client from the example and build a first draft.
# Usage: ./new-client.sh joes-pizza
set -euo pipefail
cd "$(dirname "$0")"
name="${1:?Usage: ./new-client.sh <client-name>}"
if [ -e "clients/$name" ]; then echo "clients/$name already exists"; exit 1; fi
mkdir -p "clients/$name/assets"
cp clients/_example-plumbing/site.config.json "clients/$name/site.config.json"
node build.js "clients/$name"
echo "Next: edit clients/$name/site.config.json, then run: node build.js clients/$name"
