#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo " Validating OpenAI Compute & Quota Broker         "
echo "=================================================="

python3 -m py_compile quota_broker.py
python3 quota_broker.py

echo "Validation successful!"
