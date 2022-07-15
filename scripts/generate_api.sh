#!/usr/bin/env bash
set -e

if ! [[ $(which datamodel-codegen) ]]; then
  echo "Could not locate the datamodel codegen program" >&2
  echo "    pip install datamodel-code-generator" >&2
  exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/" && pwd )"
TARGET_DIR="$( cd "$SCRIPT_DIR/../onscale_client/api" && pwd )"

cd "$SCRIPT_DIR"


echo "Generating data model"
datamodel-codegen \
    --input swagger.json \
    --output datamodel.py \
    --snake-case-field \
    --target-python-version 3.7

echo "Cleaning up generated model"
./tidy.py

echo "Moving to $TARGET_DIR"
mv datamodel.py "$TARGET_DIR"
