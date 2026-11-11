//! Artifact reactor and pressure scoring.

use chimiaclaw_artifact::Artifact;
use chimiaclaw_reputation::{ReputationDomain, ReputationOracle};
use chimiaclaw_schema::{AgentId, Capability, SchemaTag};
use std::collections::BTreeSet;

#[derive(Clone, Debug, PartialEq)]
pub struct OpenNeed {
    pub requester: AgentId,
    pub topic: String,
    pub required_tags: BTreeSet<SchemaTag>,
    pub urgency: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ReactorScore {
    pub schema_overlap: f64,
    pub capability_fit: f64,
    pub reputation: f64,
    pub pressure: f64,
}

pub fn score_need(
    need: &OpenNeed,
    agent: &AgentId,
    capabilities: &[Capability],
    reputation: &dyn ReputationOracle,
) -> ReactorScore {
    let produced: BTreeSet<SchemaTag> = capabilities
        .iter()
        .flat_map(|cap| cap.produces.clone())
        .collect();
    let overlap = need
        .required_tags
        .iter()
        .filter(|tag| produced.contains(*tag))
        .count();
    let schema_overlap = if need.required_tags.is_empty() {
        0.0
    } else {
        overlap as f64 / need.required_tags.len() as f64
    };
    let capability_fit = if overlap > 0 { 1.0 } else { 0.0 };
    let reputation_score = reputation
        .score(agent, &ReputationDomain::Optimization)
        .map_or(1.0, |score| score.decayed_score.max(0.0));
    ReactorScore {
        schema_overlap,
        capability_fit,
        reputation: reputation_score,
        pressure: need.urgency * schema_overlap * capability_fit * reputation_score,
    }
}

#[must_use]
pub fn open_needs_from_artifact(_artifact: &Artifact) -> Vec<OpenNeed> {
    // Phase 0 placeholder: real implementation reads declared unmet needs from artifact payloads.
    Vec::new()
}
