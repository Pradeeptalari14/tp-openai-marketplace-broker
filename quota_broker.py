"""Quota-aware broker for OpenAI / Azure OpenAI deployments.

Routes each request to the deployment with the best (headroom / cost) score,
tracks a sliding 60-second TPM/RPM window per deployment, honors Retry-After
cooldowns, and enforces per-tier capacity reservations.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

TIER_SHARE = {"interactive": 0.6, "batch": 0.3, "experimental": 0.1}


@dataclass
class Deployment:
    id: str
    region: str
    tpm_limit: int
    rpm_limit: int
    cost_weight: float = 1.0
    events: Deque[Tuple[float, int]] = field(default_factory=deque)
    cooldown_until: float = 0.0

    def _trim(self, now: float) -> None:
        while self.events and now - self.events[0][0] >= 60:
            self.events.popleft()

    def usage(self, now: float) -> Tuple[int, int]:
        self._trim(now)
        return sum(t for _, t in self.events), len(self.events)


class QuotaBroker:
    def __init__(self, deployments: List[Deployment], clock=time.monotonic):
        self.deployments = deployments
        self.clock = clock
        self.tier_tokens: Dict[str, Deque[Tuple[float, int]]] = {t: deque() for t in TIER_SHARE}

    def _tier_used(self, tier: str, now: float) -> int:
        q = self.tier_tokens[tier]
        while q and now - q[0][0] >= 60:
            q.popleft()
        return sum(t for _, t in q)

    def select(self, est_tokens: int, tier: str = "interactive", region: Optional[str] = None) -> Optional[Deployment]:
        now = self.clock()
        pool = [d for d in self.deployments if region is None or d.region == region]
        # Tier shares are reserved against the whole pool's capacity, not a region subset.
        total_tpm = sum(d.tpm_limit for d in self.deployments)
        if self._tier_used(tier, now) + est_tokens > TIER_SHARE[tier] * total_tpm:
            return None  # tier budget exhausted
        best, best_score = None, -1.0
        for d in pool:
            if now < d.cooldown_until:
                continue
            tpm_used, rpm_used = d.usage(now)
            tpm_left, rpm_left = d.tpm_limit - tpm_used, d.rpm_limit - rpm_used
            if tpm_left < est_tokens or rpm_left < 1:
                continue
            score = min(tpm_left / d.tpm_limit, rpm_left / d.rpm_limit) / d.cost_weight
            if score > best_score:
                best, best_score = d, score
        return best

    def record(self, d: Deployment, tokens: int, tier: str = "interactive") -> None:
        now = self.clock()
        d.events.append((now, tokens))
        self.tier_tokens[tier].append((now, tokens))

    def mark_rate_limited(self, d: Deployment, retry_after_s: float) -> None:
        d.cooldown_until = self.clock() + retry_after_s


def main() -> None:
    t = [0.0]
    broker = QuotaBroker(
        [
            Deployment("openai-primary", "global", tpm_limit=20000, rpm_limit=100),
            Deployment("azure-eastus2", "eastus2", tpm_limit=10000, rpm_limit=60, cost_weight=0.95),
            Deployment("azure-swedencentral", "swedencentral", tpm_limit=8000, rpm_limit=48, cost_weight=0.95),
        ],
        clock=lambda: t[0],
    )
    counts: Dict[str, int] = {}
    for _ in range(20):
        d = broker.select(1000)
        assert d is not None
        broker.record(d, 1000)
        counts[d.id] = counts.get(d.id, 0) + 1
    print("Distribution after 20 requests:", counts)
    assert len(counts) >= 2, "load should spread across deployments"

    primary = broker.deployments[0]
    broker.mark_rate_limited(primary, retry_after_s=30)
    assert broker.select(1000).id != primary.id, "cooled-down deployment must be skipped"

    eu = broker.select(500, region="swedencentral")
    assert eu is not None and eu.region == "swedencentral"

    # Experimental tier gets 10% of 38k TPM = 3.8k; a 4k request must be refused.
    assert broker.select(4000, tier="experimental") is None, "tier budget must be enforced"
    t[0] = 61.0  # window slides; capacity frees up
    assert broker.deployments[1].usage(t[0]) == (0, 0)
    print("Broker validation passed.")


if __name__ == "__main__":
    main()
