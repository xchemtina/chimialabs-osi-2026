//! Skill trait and registry.

use chimiaclaw_artifact::{Artifact, ArtifactDraft};
use chimiaclaw_schema::{AgentId, Capability, SchemaTag, SkillId};
use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct SkillCtx {
    pub agent: AgentId,
    pub topic: String,
}

#[derive(Debug, Eq, PartialEq)]
pub enum SkillError {
    InvalidInput(String),
    Execution(String),
}

pub trait Skill: Send + Sync {
    fn id(&self) -> SkillId;
    fn capabilities(&self) -> Vec<Capability>;
    fn consumes_tags(&self) -> Vec<SchemaTag>;
    fn produces_tags(&self) -> Vec<SchemaTag>;
    fn invoke(&self, ctx: &SkillCtx, parents: &[Artifact]) -> Result<ArtifactDraft, SkillError>;
}

#[derive(Default)]
pub struct SkillRegistry {
    skills: BTreeMap<SkillId, Box<dyn Skill>>,
}

impl SkillRegistry {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, skill: Box<dyn Skill>) {
        self.skills.insert(skill.id(), skill);
    }

    #[must_use]
    pub fn get(&self, id: &SkillId) -> Option<&dyn Skill> {
        self.skills.get(id).map(std::convert::AsRef::as_ref)
    }

    #[must_use]
    pub fn ids(&self) -> Vec<SkillId> {
        self.skills.keys().cloned().collect()
    }
}
