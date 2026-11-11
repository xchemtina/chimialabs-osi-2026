//! Agent heartbeat and execution shell.

use chimiaclaw_artifact::{Artifact, ArtifactStore};
use chimiaclaw_reactor::OpenNeed;
use chimiaclaw_schema::AgentId;
use chimiaclaw_skill::SkillRegistry;

pub struct AgentProfile {
    pub id: AgentId,
    pub strategy_sets: Vec<String>,
}

pub struct AgentRuntime<S: ArtifactStore> {
    pub profile: AgentProfile,
    pub store: S,
    pub skills: SkillRegistry,
}

impl<S: ArtifactStore> AgentRuntime<S> {
    #[must_use]
    pub fn profile(&self) -> &AgentProfile {
        &self.profile
    }

    pub fn heartbeat(&self) -> AgentHeartbeatReport {
        AgentHeartbeatReport {
            agent: self.profile.id.clone(),
            observed_artifacts: 0,
            open_needs: Vec::new(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct AgentHeartbeatReport {
    pub agent: AgentId,
    pub observed_artifacts: usize,
    pub open_needs: Vec<OpenNeed>,
}

pub trait ArtifactPublisher {
    fn publish(&mut self, artifact: Artifact) -> Result<(), String>;
}
