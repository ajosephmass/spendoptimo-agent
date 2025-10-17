#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npx cdk destroy --all --force
echo "Destroyed SpendOptimo stacks."
