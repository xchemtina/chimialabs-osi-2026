//! PoX-aligned reputation primitives.

use chimiaclaw_schema::AgentId;

#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd, Hash)]
pub enum ReputationDomain {
    Hplc,
    Nmr,
    Pxrd,
    MsMs,
    Retrosynth,
    Dft,
    Governance,
    Optimization,
    Custom(String),
}

#[derive(Clone, Debug, PartialEq)]
pub struct ReputationScore {
    pub agent: AgentId,
    pub domain: ReputationDomain,
    pub raw_score: f64,
    pub decayed_score: f64,
    pub snapshot_block: u64,
}

pub trait ReputationOracle {
    fn score(&self, agent: &AgentId, domain: &ReputationDomain) -> Option<ReputationScore>;
}

#[derive(Default)]
pub struct NullReputationOracle;

impl ReputationOracle for NullReputationOracle {
    fn score(&self, agent: &AgentId, domain: &ReputationDomain) -> Option<ReputationScore> {
        Some(ReputationScore {
            agent: agent.clone(),
            domain: domain.clone(),
            raw_score: 1.0,
            decayed_score: 1.0,
            snapshot_block: 0,
        })
    }
}
