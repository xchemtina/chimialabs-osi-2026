//! Minimal local runtime for ChimiaClaw nodes.
//!
//! This is intentionally simple: a node loads a profile, opens a file-backed
//! artifact store, and runs polling loops that scan for parent artifacts whose
//! schema tags match a registered skill's `consumes_tags`. For each match, the
//! node invokes the skill, seals the resulting draft with its signer, and
//! writes the child artifact back to the store.
//!
//! It does not yet implement reactor scoring, capabilities, transport, or
//! distributed scheduling. It is the smallest honest step from "manual demo
//! orchestration" toward "agents do work autonomously".
//!
//! The development signer seed in [`NodeProfile::dev_signer_from_seed_label`]
//! is for local testing only; production keys must not be derived this way.
//!
//! # Example
//! ```no_run
//! use chimiaclaw_artifact::ArtifactSigner;
//! use chimiaclaw_node::{NodeProfile, NodeRuntime};
//! use chimiaclaw_schema::AgentId;
//! use std::path::PathBuf;
//!
//! let profile = NodeProfile {
//!     agent: AgentId("local.dev.eth".to_string()),
//!     signer: ArtifactSigner::from_seed([3; 32]),
//!     store_dir: PathBuf::from("./.chimiaclaw/store"),
//! };
//! let mut runtime = NodeRuntime::open(profile).expect("open");
//! // runtime.register_skill(...);
//! let _report = runtime.run_once(0).expect("run-once");
//! ```

use chimiaclaw_artifact::{
    blake3_hex, Artifact, ArtifactError, ArtifactId, ArtifactSigner, ArtifactStore,
    ArtifactStoreError, FileArtifactStore,
};
use chimiaclaw_schema::{AgentId, SchemaTag, SkillId};
use chimiaclaw_skill::{Skill, SkillCtx, SkillError, SkillRegistry};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::Duration;

/// A local runtime profile: agent identity, signer, and store directory.
pub struct NodeProfile {
    pub agent: AgentId,
    pub signer: ArtifactSigner,
    pub store_dir: PathBuf,
}

impl NodeProfile {
    /// Build a development signer from a stable label, so that demo runs are
    /// reproducible without any real key management. **Do not use this for
    /// production keys.**
    #[must_use]
    pub fn dev_signer_from_seed_label(label: &str) -> ArtifactSigner {
        let digest = blake3_hex(format!("chimiaclaw-dev-seed:{label}").as_bytes());
        let mut seed = [0u8; 32];
        let bytes = hex_decode_first_32(&digest);
        seed.copy_from_slice(&bytes);
        ArtifactSigner::from_seed(seed)
    }
}

fn hex_decode_first_32(hex: &str) -> Vec<u8> {
    // hex strings produced by blake3 are 64 hex chars; we take the first 64.
    let trimmed = &hex[..64];
    (0..32)
        .map(|i| {
            let pair = &trimmed[i * 2..i * 2 + 2];
            u8::from_str_radix(pair, 16).unwrap_or(0)
        })
        .collect()
}

/// Errors that can occur while running the node.
#[derive(Debug)]
pub enum NodeError {
    Store(ArtifactStoreError),
    Artifact(ArtifactError),
    Skill(SkillError),
}

impl From<ArtifactStoreError> for NodeError {
    fn from(value: ArtifactStoreError) -> Self {
        Self::Store(value)
    }
}

impl From<ArtifactError> for NodeError {
    fn from(value: ArtifactError) -> Self {
        Self::Artifact(value)
    }
}

/// One execution of the node's run-once loop.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunOnceReport {
    pub agent: AgentId,
    pub store_dir: PathBuf,
    pub invocations: Vec<SkillInvocation>,
}

/// One cycle in a repeated local polling loop.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunCycleReport {
    pub cycle_index: u64,
    pub created_at_unix: u64,
    pub report: RunOnceReport,
}

/// Per-skill summary of a run-once iteration.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SkillInvocation {
    pub skill: SkillId,
    pub matched_parents: Vec<ArtifactId>,
    pub produced_children: Vec<ArtifactId>,
    pub skipped_existing: Vec<ArtifactId>,
    pub failures: Vec<SkillFailure>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SkillFailure {
    pub parent: ArtifactId,
    pub reason: String,
}

/// File-backed local node runtime with a `SkillRegistry`.
pub struct NodeRuntime {
    profile: NodeProfile,
    store: FileArtifactStore,
    skills: SkillRegistry,
}

impl NodeRuntime {
    /// Open or create the file-backed store described by `profile`.
    pub fn open(profile: NodeProfile) -> Result<Self, NodeError> {
        let store = FileArtifactStore::open(&profile.store_dir)?;
        Ok(Self {
            profile,
            store,
            skills: SkillRegistry::new(),
        })
    }

    /// Register a skill that the runtime can invoke.
    pub fn register_skill(&mut self, skill: Box<dyn Skill>) {
        self.skills.register(skill);
    }

    /// Persist a starter artifact (e.g. a seed ORD reaction or route proposal)
    /// into the store. Useful for tests and CLI bootstrapping.
    pub fn put_artifact(&mut self, artifact: Artifact) -> Result<(), NodeError> {
        self.store.put(artifact)?;
        Ok(())
    }

    /// Read an artifact by id.
    pub fn get_artifact(&self, id: &ArtifactId) -> Result<Option<Artifact>, NodeError> {
        Ok(self.store.get(id)?)
    }

    /// Read all artifacts currently in the store, sorted by id.
    pub fn all_artifacts(&self) -> Result<Vec<Artifact>, NodeError> {
        Ok(self.store.all()?)
    }

    /// Run one synchronous pass over the store. For each registered skill,
    /// find parent artifacts whose `schema_tags` match the skill's
    /// `consumes_tags` and invoke the skill on them.
    pub fn run_once(&mut self, created_at_unix: u64) -> Result<RunOnceReport, NodeError> {
        let all = self.store.all()?;
        let skill_ids = self.skills.ids();
        let mut invocations = Vec::new();
        for skill_id in skill_ids {
            let invocation = self.run_skill(&skill_id, &all, created_at_unix)?;
            invocations.push(invocation);
        }
        Ok(RunOnceReport {
            agent: self.profile.agent.clone(),
            store_dir: self.profile.store_dir.clone(),
            invocations,
        })
    }

    /// Run a finite polling loop. This is primarily for tests and scripted
    /// demos; CLI daemon mode can keep calling [`Self::run_once`] forever.
    pub fn run_for_cycles(
        &mut self,
        cycles: u64,
        interval: Duration,
        created_at_start_unix: u64,
    ) -> Result<Vec<RunCycleReport>, NodeError> {
        let mut reports = Vec::new();
        for cycle_index in 0..cycles {
            let created_at_unix = created_at_start_unix.saturating_add(cycle_index);
            let report = self.run_once(created_at_unix)?;
            reports.push(RunCycleReport {
                cycle_index,
                created_at_unix,
                report,
            });
            if cycle_index + 1 < cycles && !interval.is_zero() {
                std::thread::sleep(interval);
            }
        }
        Ok(reports)
    }

    fn run_skill(
        &mut self,
        skill_id: &SkillId,
        artifacts: &[Artifact],
        created_at_unix: u64,
    ) -> Result<SkillInvocation, NodeError> {
        let mut matched_parents = Vec::new();
        let mut produced_children = Vec::new();
        let mut skipped_existing = Vec::new();
        let mut failures = Vec::new();

        // We must clone the skill metadata before sealing because the registry
        // borrows immutably while seal needs the runtime signer.
        let consumes: Vec<SchemaTag>;
        {
            let skill = self.skills.get(skill_id).expect("skill in registry");
            consumes = skill.consumes_tags();
        }

        for parent in artifacts {
            if !consumes.iter().any(|tag| parent.schema_tags.contains(tag)) {
                continue;
            }
            matched_parents.push(parent.id.clone());
            if let Some(existing_child) = artifacts
                .iter()
                .find(|candidate| candidate.skill == *skill_id && candidate.has_parent(&parent.id))
            {
                skipped_existing.push(existing_child.id.clone());
                continue;
            }

            let draft_result = {
                let skill = self.skills.get(skill_id).expect("skill in registry");
                let ctx = SkillCtx {
                    agent: self.profile.agent.clone(),
                    topic: parent.topic.clone(),
                };
                skill.invoke(&ctx, std::slice::from_ref(parent))
            };
            let draft = match draft_result {
                Ok(draft) => draft,
                Err(error) => {
                    failures.push(SkillFailure {
                        parent: parent.id.clone(),
                        reason: format!("{error:?}"),
                    });
                    continue;
                }
            };

            let sealed = match draft.seal(&self.profile.signer, created_at_unix) {
                Ok(sealed) => sealed,
                Err(error) => {
                    failures.push(SkillFailure {
                        parent: parent.id.clone(),
                        reason: format!("seal failed: {error:?}"),
                    });
                    continue;
                }
            };

            match self.store.put(sealed.clone()) {
                Ok(()) => produced_children.push(sealed.id),
                Err(ArtifactStoreError::Conflict(id)) => {
                    skipped_existing.push(id);
                }
                Err(other) => return Err(NodeError::Store(other)),
            }
        }

        Ok(SkillInvocation {
            skill: skill_id.clone(),
            matched_parents,
            produced_children,
            skipped_existing,
            failures,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chimiaclaw_artifact::{ArtifactDraft, PayloadRef};
    use chimiaclaw_schema::{Capability, SchemaTag, SkillId};
    use std::collections::BTreeSet;

    struct DoublingSkill;

    impl Skill for DoublingSkill {
        fn id(&self) -> SkillId {
            SkillId("test.double.v1".to_string())
        }
        fn capabilities(&self) -> Vec<Capability> {
            Vec::new()
        }
        fn consumes_tags(&self) -> Vec<SchemaTag> {
            vec![SchemaTag("test.input".to_string())]
        }
        fn produces_tags(&self) -> Vec<SchemaTag> {
            vec![SchemaTag("test.output".to_string())]
        }
        fn invoke(
            &self,
            ctx: &SkillCtx,
            parents: &[Artifact],
        ) -> Result<ArtifactDraft, SkillError> {
            let parent = parents
                .first()
                .ok_or_else(|| SkillError::InvalidInput("missing parent".to_string()))?;
            let payload = PayloadRef::inline_json(&format!("doubled:{}", parent.topic))
                .map_err(|e| SkillError::Execution(format!("payload: {e:?}")))?;
            Ok(ArtifactDraft {
                skill: self.id(),
                agent: ctx.agent.clone(),
                topic: format!("doubled-{}", parent.topic),
                input_fingerprint: parent.content_hash.clone(),
                output_cid: None,
                parent_artifact_ids: vec![parent.id.clone()],
                schema_tags: BTreeSet::from([SchemaTag("test.output".to_string())]),
                payload: Some(payload),
            })
        }
    }

    fn temp_store_dir(tag: &str) -> PathBuf {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let count = COUNTER.fetch_add(1, Ordering::Relaxed);
        let mut path = std::env::temp_dir();
        path.push(format!(
            "chimiaclaw-node-{tag}-{nanos}-{}-{count}",
            std::process::id()
        ));
        path
    }

    fn parent_artifact(signer: &ArtifactSigner, topic: &str) -> Artifact {
        let payload = PayloadRef::inline_json(&topic.to_string()).expect("payload");
        ArtifactDraft {
            skill: SkillId("test.seed.v1".to_string()),
            agent: AgentId("seed.local.eth".to_string()),
            topic: topic.to_string(),
            input_fingerprint: "input:test".to_string(),
            output_cid: None,
            parent_artifact_ids: Vec::new(),
            schema_tags: BTreeSet::from([SchemaTag("test.input".to_string())]),
            payload: Some(payload),
        }
        .seal(signer, 0)
        .expect("seal seed")
    }

    #[test]
    fn run_once_invokes_registered_skill_and_persists_child() {
        let dir = temp_store_dir("invoke");
        let signer = ArtifactSigner::from_seed([5; 32]);
        let parent = parent_artifact(&signer, "alpha");

        let profile = NodeProfile {
            agent: AgentId("test.local.eth".to_string()),
            signer: ArtifactSigner::from_seed([6; 32]),
            store_dir: dir.clone(),
        };
        let mut runtime = NodeRuntime::open(profile).expect("open");
        runtime.put_artifact(parent.clone()).expect("seed");
        runtime.register_skill(Box::new(DoublingSkill));

        let report = runtime.run_once(1).expect("run once");
        assert_eq!(report.invocations.len(), 1);
        let invocation = &report.invocations[0];
        assert_eq!(invocation.matched_parents, vec![parent.id.clone()]);
        assert_eq!(invocation.produced_children.len(), 1);
        assert!(invocation.failures.is_empty());

        let stored = runtime.all_artifacts().expect("all");
        assert_eq!(stored.len(), 2);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn run_once_is_idempotent_for_already_present_children() {
        let dir = temp_store_dir("idem");
        let signer = ArtifactSigner::from_seed([7; 32]);
        let parent = parent_artifact(&signer, "beta");
        let profile = NodeProfile {
            agent: AgentId("test.local.eth".to_string()),
            signer: ArtifactSigner::from_seed([8; 32]),
            store_dir: dir.clone(),
        };
        let mut runtime = NodeRuntime::open(profile).expect("open");
        runtime.put_artifact(parent.clone()).expect("seed");
        runtime.register_skill(Box::new(DoublingSkill));

        let first = runtime.run_once(2).expect("first");
        assert_eq!(first.invocations[0].produced_children.len(), 1);

        let second = runtime.run_once(999).expect("second");
        let invocation = &second.invocations[0];
        assert_eq!(invocation.produced_children.len(), 0);
        assert_eq!(invocation.skipped_existing.len(), 1);
        std::fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn finite_polling_loop_does_not_duplicate_existing_children() {
        let dir = temp_store_dir("poll");
        let signer = ArtifactSigner::from_seed([9; 32]);
        let parent = parent_artifact(&signer, "gamma");
        let profile = NodeProfile {
            agent: AgentId("test.local.eth".to_string()),
            signer: ArtifactSigner::from_seed([10; 32]),
            store_dir: dir.clone(),
        };
        let mut runtime = NodeRuntime::open(profile).expect("open");
        runtime.put_artifact(parent).expect("seed");
        runtime.register_skill(Box::new(DoublingSkill));

        let reports = runtime
            .run_for_cycles(3, Duration::ZERO, 100)
            .expect("poll");
        assert_eq!(reports.len(), 3);
        assert_eq!(reports[0].report.invocations[0].produced_children.len(), 1);
        assert_eq!(reports[1].report.invocations[0].produced_children.len(), 0);
        assert_eq!(reports[2].report.invocations[0].produced_children.len(), 0);
        assert_eq!(runtime.all_artifacts().expect("all").len(), 2);
        std::fs::remove_dir_all(&dir).ok();
    }
}
