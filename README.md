# OpenAI Compute & Quota Broker (`tp-openai-marketplace-broker`)

[![CI](https://github.com/Pradeeptalari14/tp-openai-marketplace-broker/actions/workflows/broker-ci.yml/badge.svg)](https://github.com/Pradeeptalari14/tp-openai-marketplace-broker/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](https://python.org)

Quota-aware request routing across multiple **OpenAI** and **Azure OpenAI** deployments. Stops HTTP 429s on one deployment while others sit idle by treating them all as a single pool.

---

## 🏗️ Architecture

![Broker Flow](docs/openai_marketplace_flow.png)

```mermaid
flowchart LR
    App["Apps / Agents"] --> Broker["Quota Broker"]
    Broker --> Tier["Tier Budget Check (interactive / batch / experimental)"]
    Tier --> Score["Headroom Score = min(TPM%, RPM%) / cost"]
    Score --> D1["OpenAI (global)"]
    Score --> D2["Azure OpenAI eastus2"]
    Score --> D3["Azure OpenAI swedencentral (EU)"]
    D1 & D2 & D3 -. 429 + Retry-After .-> Cool["Cooldown"] -.-> Score
```

---

## 🚀 Features

| Feature | How it works |
|---|---|
| Sliding-window quotas | Tracks tokens and requests per deployment over the last 60s |
| Headroom routing | Picks the deployment with the most remaining capacity per unit cost |
| `Retry-After` cooldowns | A rate-limited deployment is skipped until its cooldown ends |
| Priority tiers | Interactive 60% / Batch 30% / Experimental 10% of pool TPM |
| Data residency | `region=` filter keeps EU traffic on EU deployments |

---

## 📦 Quickstart

```bash
bash scripts/validate.sh
```

```python
from quota_broker import QuotaBroker, Deployment

broker = QuotaBroker([
    Deployment("openai-primary", "global", tpm_limit=2_000_000, rpm_limit=10_000),
    Deployment("azure-eastus2", "eastus2", tpm_limit=1_000_000, rpm_limit=6_000, cost_weight=0.95),
])
d = broker.select(est_tokens=1500, tier="interactive")
if d is None:
    ...  # queue with backoff or return 429
else:
    # call the client bound to d.id, then:
    broker.record(d, tokens=1500)
    # on RateLimitError: broker.mark_rate_limited(d, retry_after_s=float(headers["retry-after"]))
```

---

## 📄 License & Security

MIT — see [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).
