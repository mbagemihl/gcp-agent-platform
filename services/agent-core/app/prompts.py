"""Prompt templates and deterministic policy risk evaluation for RFP analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SYSTEM_INSTRUCTION = """You are the Enterprise Architecture & Compliance RFP Agent for a GCP-focused consulting organization.
Your task is to evaluate incoming Requests for Proposals (RFPs) against:
1. Internal Enterprise Policies retrieved from Vertex AI RAG (Cloud-First, Security/GDPR, Open-Source Licensing, Commercial Liability).
2. Live consulting rates and delivery availability retrieved from the MCP Pricing Server.

Always produce a structured German or English executive assessment (matching the user's prompt language) containing:
- **Ampel-Status & Risiko-Score** (GREEN / YELLOW / RED)
- **Policy-Compliance & Blocker-Analyse** (citing retrieved policies)
- **Team- & Kalkulationsschätzung** (using the live MCP daily rates & availability)
- **Klare Go / No-Go Empfehlung** with concrete next actions.
"""


@dataclass(frozen=True)
class PolicyRule:
    """Rule definition mapping RFP keywords to policy risks and score penalties."""

    rule_id: str
    severity: str
    score_impact: int
    keywords: tuple[str, ...]
    description: str


POLICY_RULES: tuple[PolicyRule, ...] = (
    PolicyRule(
        rule_id="CLOUD_FIRST_AIRGAP",
        severity="blocker",
        score_impact=38,
        keywords=("air-gapped", "air gapped", "on-prem only", "on-premises only", "kein cloud", "no public cloud", "strictly on-prem"),
        description="Mandates strictly on-premises / air-gapped deployment, violating Enterprise Cloud-First GCP Strategy.",
    ),
    PolicyRule(
        rule_id="OSS_VIRAL_LICENSE",
        severity="blocker",
        score_impact=32,
        keywords=("agpl", "gplv3", "gpl-3.0", "viral open source", "copyleft"),
        description="Requires AGPL/GPLv3 viral copyleft licensing for core deliverables, violating Open-Source IP Policy.",
    ),
    PolicyRule(
        rule_id="UNLIMITED_LIABILITY",
        severity="blocker",
        score_impact=28,
        keywords=("unlimited liability", "unbegrenzte haftung", "uncapped liability", "unbeschränkte haftung"),
        description="Requires unlimited financial liability, violating Commercial Governance Policy (cap: 1x contract value).",
    ),
    PolicyRule(
        rule_id="SECURITY_COMPLIANCE_WAIVER",
        severity="warning",
        score_impact=15,
        keywords=("root access", "disable encryption", "unencrypted", "no audit log", "legacy tls 1.0"),
        description="Requests weakened encryption or audit controls requiring CISO security waiver.",
    ),
    PolicyRule(
        rule_id="TIGHT_TIMELINE_PENALTY",
        severity="warning",
        score_impact=12,
        keywords=("liquidated damages", "vertragsstrafe", "48h go-live", "immediate start"),
        description="Contains strict SLA penalty clauses or aggressive onboarding timelines.",
    ),
)

ROLE_KEYWORD_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Cloud Architect", ("gcp", "cloud", "kubernetes", "gke", "cloud run", "terraform", "architecture", "architektur")),
    ("AI Engineer", ("ai", "llm", "gemini", "vertex", "rag", "agent", "ki", "machine learning")),
    ("Security Architect", ("security", "gdpr", "dsgvo", "iso 27001", "iam", "compliance", "zero trust", "sicherheit")),
    ("Data Engineer", ("data", "bigquery", "firestore", "pipeline", "etl", "analytics", "daten")),
    ("DevSecOps Engineer", ("ci/cd", "github actions", "devsecops", "docker", "container", "observability", "trace")),
    ("Project Manager", ("project management", "pmo", "scrum", "stakeholder", "milestone", "steuerung")),
)


def extract_required_roles(rfp_text: str) -> list[str]:
    """Identify consulting roles needed for the RFP based on technical signals."""
    lower_text = rfp_text.lower()
    matched = [role for role, keywords in ROLE_KEYWORD_MAP if any(kw in lower_text for kw in keywords)]
    if not matched:
        return ["Cloud Architect", "AI Engineer"]
    if "Cloud Architect" not in matched:
        matched.insert(0, "Cloud Architect")
    return matched[:4]


def evaluate_policy_risk(rfp_text: str, rag_contexts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Evaluate RFP text against enterprise policy rules and return score, blockers, and roles."""
    lower_text = rfp_text.lower()
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    score = 12  # baseline operational delivery risk

    for rule in POLICY_RULES:
        hits = [kw for kw in rule.keywords if kw in lower_text]
        if not hits:
            continue
        finding = {
            "rule_id": rule.rule_id,
            "severity": rule.severity,
            "matched_terms": hits,
            "description": rule.description,
        }
        score += rule.score_impact
        if rule.severity == "blocker":
            blockers.append(finding)
        else:
            warnings.append(finding)

    # Slightly reduce baseline risk if explicit positive GCP cloud-native alignment is present and no blockers
    positive_signals = ("gcp", "google cloud", "cloud run", "vertex ai", "apache-2.0", "mit license", "iso 27001")
    positive_hits = sum(1 for kw in positive_signals if kw in lower_text)
    if not blockers and positive_hits >= 2:
        score = max(10, score - 4)

    clamped_score = max(0, min(100, score))
    if clamped_score < 40:
        status = "GREEN"
    elif clamped_score < 70:
        status = "YELLOW"
    else:
        status = "RED"

    return {
        "risk_score": clamped_score,
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "required_roles": extract_required_roles(rfp_text),
        "rag_policies_evaluated": len(rag_contexts or []),
    }


def build_analysis_prompt(
    rfp_title: str,
    rfp_text: str,
    user_query: str,
    rag_contexts: list[dict[str, Any]],
    role_rates: list[dict[str, Any]],
    risk_assessment: dict[str, Any] | None = None,
) -> str:
    """Assemble a grounded prompt combining RFP content, RAG policies, and MCP rate data."""
    policies_block = "\n".join(
        f"- [{ctx.get('title', 'Policy')}] (score={ctx.get('score', 0.0):.2f}): {ctx.get('text', '').strip()}"
        for ctx in rag_contexts
    ) or "- No external policies retrieved."

    rates_block = "\n".join(
        f"- {rate.get('matched_role', rate.get('role'))}: {rate.get('daily_rate_eur')} EUR/day "
        f"(Availability: {rate.get('availability')}, FTE: {rate.get('available_fte')}, Lead time: {rate.get('lead_time_weeks')}w)"
        for rate in role_rates
    ) or "- No role rates retrieved."

    assessment = risk_assessment or evaluate_policy_risk(rfp_text, rag_contexts)
    blockers_text = (
        "\n".join(f"- [{b['rule_id']}] {b['description']}" for b in assessment["blockers"])
        or "- None detected"
    )

    return f"""### RFP Title
{rfp_title}

### User Question / Instruction
{user_query}

### RFP Content
{rfp_text}

### Retrieved Enterprise Policies (Vertex AI RAG)
{policies_block}

### Live Consulting Rates & Availability (MCP Pricing Server)
{rates_block}

### Automated Pre-Check
- Preliminary Risk Score: {assessment['risk_score']}/100 ({assessment['status']})
- Detected Policy Blockers:
{blockers_text}

Please provide a concise, well-structured compliance & pricing evaluation in German with a clear Go/No-Go recommendation.
"""
