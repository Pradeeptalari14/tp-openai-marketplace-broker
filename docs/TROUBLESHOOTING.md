# 🔧 Troubleshooting Guide — OpenAI Compute & Quota Broker Studio

## Issue 1: Deployment Container Crash / High Memory Pressure
**Symptom:** Process exits with code 137 (OOMKilled)
**Resolution:**
- Check memory allocations in `.env.example` and increase container memory limit.
- Run `bash scripts/validate.sh` to verify parameter constraints.

## Issue 2: Connectivity Handshake Timeout
**Symptom:** Network connection timed out on upstream endpoint
**Resolution:**
- Verify firewall rules and security group egress permissions.
- Validate that the target service hostname is resolvable via cluster DNS.
