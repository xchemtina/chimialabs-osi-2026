//! File-backed implementation of [`ArtifactStore`].
//!
//! Each artifact is persisted as a deterministic JSON file under a single
//! directory using its `art_<id>.json` filename. Verification is enforced on
//! both write and read so a tampered file is rejected before re-entering the
//! in-memory view of the DAG.
//!
//! This is intentionally minimal -- no databases, no concurrency control --
//! and it complements [`InMemoryArtifactStore`] for hackathon-grade local
//! runtime persistence.

use crate::{Artifact, ArtifactId, ArtifactStore, ArtifactStoreError};
use std::fs;
use std::path::{Path, PathBuf};

/// Directory-backed artifact store. Each artifact is one JSON file.
pub struct FileArtifactStore {
    root: PathBuf,
}

impl FileArtifactStore {
    /// Open or create a store rooted at `path`. Creates the directory
    /// recursively if it does not exist yet.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, ArtifactStoreError> {
        let root = path.as_ref().to_path_buf();
        fs::create_dir_all(&root)
            .map_err(|error| ArtifactStoreError::Backend(error.to_string()))?;
        Ok(Self { root })
    }

    /// Filesystem path that an artifact id maps to.
    #[must_use]
    pub fn path_for(&self, id: &ArtifactId) -> PathBuf {
        self.root.join(format!("{}.json", id.0))
    }

    /// Root directory of this store.
    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    fn read_one(&self, path: &Path) -> Result<Artifact, ArtifactStoreError> {
        let bytes =
            fs::read(path).map_err(|error| ArtifactStoreError::Backend(error.to_string()))?;
        let artifact: Artifact = serde_json::from_slice(&bytes)
            .map_err(|error| ArtifactStoreError::Backend(error.to_string()))?;
        artifact.verify().map_err(ArtifactStoreError::Invalid)?;
        Ok(artifact)
    }
}

impl ArtifactStore for FileArtifactStore {
    fn put(&mut self, artifact: Artifact) -> Result<(), ArtifactStoreError> {
        artifact.verify().map_err(ArtifactStoreError::Invalid)?;
        let path = self.path_for(&artifact.id);
        if path.exists() {
            return Err(ArtifactStoreError::Conflict(artifact.id));
        }
        let bytes = serde_json::to_vec_pretty(&artifact)
            .map_err(|error| ArtifactStoreError::Backend(error.to_string()))?;
        fs::write(&path, bytes).map_err(|error| ArtifactStoreError::Backend(error.to_string()))?;
        Ok(())
    }

    fn get(&self, id: &ArtifactId) -> Result<Option<Artifact>, ArtifactStoreError> {
        let path = self.path_for(id);
        if !path.exists() {
            return Ok(None);
        }
        Ok(Some(self.read_one(&path)?))
    }

    fn children_of(&self, id: &ArtifactId) -> Result<Vec<Artifact>, ArtifactStoreError> {
        Ok(self
            .all()?
            .into_iter()
            .filter(|artifact| artifact.has_parent(id))
            .collect())
    }

    fn all(&self) -> Result<Vec<Artifact>, ArtifactStoreError> {
        let mut artifacts = Vec::new();
        let entries = match fs::read_dir(&self.root) {
            Ok(entries) => entries,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(artifacts),
            Err(error) => return Err(ArtifactStoreError::Backend(error.to_string())),
        };
        for entry in entries {
            let entry = entry.map_err(|error| ArtifactStoreError::Backend(error.to_string()))?;
            let path = entry.path();
            if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
                continue;
            }
            artifacts.push(self.read_one(&path)?);
        }
        artifacts.sort_by(|a, b| a.id.cmp(&b.id));
        Ok(artifacts)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{ArtifactDraft, ArtifactSigner, PayloadRef};
    use chimiaclaw_schema::{AgentId, SchemaTag, SkillId};
    use serde::{Deserialize, Serialize};
    use std::collections::BTreeSet;

    #[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
    struct DemoPayload {
        molecule: String,
    }

    fn temp_dir() -> PathBuf {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let count = COUNTER.fetch_add(1, Ordering::Relaxed);
        let mut path = std::env::temp_dir();
        path.push(format!(
            "chimiaclaw-store-{nanos}-{}-{count}",
            std::process::id()
        ));
        path
    }

    fn payload_artifact(parent: Vec<ArtifactId>, payload: PayloadRef) -> Artifact {
        ArtifactDraft {
            skill: SkillId("chem.demo.v1".to_string()),
            agent: AgentId("worker.demo.eth".to_string()),
            topic: "demo".to_string(),
            input_fingerprint: "input:demo".to_string(),
            output_cid: None,
            parent_artifact_ids: parent,
            schema_tags: BTreeSet::from([SchemaTag("chem.demo".to_string())]),
            payload: Some(payload),
        }
        .seal(&ArtifactSigner::from_seed([13; 32]), 1)
        .expect("seal demo")
    }

    #[test]
    fn round_trips_artifact_through_disk() {
        let dir = temp_dir();
        {
            let mut store = FileArtifactStore::open(&dir).expect("open");
            let payload = PayloadRef::inline_json(&DemoPayload {
                molecule: "H2O".to_string(),
            })
            .expect("payload");
            let artifact = payload_artifact(Vec::new(), payload);
            store.put(artifact.clone()).expect("put");
            let fetched = store.get(&artifact.id).expect("get").expect("present");
            assert_eq!(fetched, artifact);
        }
        // Reopen the store in a new process-like scope to prove restart.
        let store = FileArtifactStore::open(&dir).expect("reopen");
        let all = store.all().expect("all");
        assert_eq!(all.len(), 1);
        all[0].verify().expect("survives reload");
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_conflicting_put() {
        let dir = temp_dir();
        let mut store = FileArtifactStore::open(&dir).expect("open");
        let payload = PayloadRef::inline_json(&DemoPayload {
            molecule: "CO2".to_string(),
        })
        .expect("payload");
        let artifact = payload_artifact(Vec::new(), payload);
        store.put(artifact.clone()).expect("put");
        let err = store.put(artifact.clone()).expect_err("conflict");
        assert!(matches!(err, ArtifactStoreError::Conflict(_)));
        fs::remove_dir_all(&dir).ok();
    }

    #[test]
    fn rejects_tampered_file_on_read() {
        let dir = temp_dir();
        let mut store = FileArtifactStore::open(&dir).expect("open");
        let payload = PayloadRef::inline_json(&DemoPayload {
            molecule: "NH3".to_string(),
        })
        .expect("payload");
        let artifact = payload_artifact(Vec::new(), payload);
        store.put(artifact.clone()).expect("put");

        // Mutate the persisted JSON in a way that breaks verification.
        let path = store.path_for(&artifact.id);
        let raw = fs::read_to_string(&path).expect("read disk");
        let tampered = raw.replace("\"demo\"", "\"forged\"");
        fs::write(&path, tampered).expect("write tampered");

        let err = store.get(&artifact.id).expect_err("rejected");
        assert!(matches!(err, ArtifactStoreError::Invalid(_)));
        fs::remove_dir_all(&dir).ok();
    }
}
