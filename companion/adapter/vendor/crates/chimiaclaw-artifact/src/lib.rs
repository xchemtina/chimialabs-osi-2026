//! Signed artifact model and store traits.
//!
//! Artifacts commit to their scientific or procurement payload through a
//! `PayloadRef` so that the signed metadata is bound to the canonical bytes of
//! the payload it represents. Tampering with the payload invalidates the
//! signed `content_hash`.

use chimiaclaw_schema::{AgentId, SchemaTag, SkillId};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

mod file_store;
pub use file_store::FileArtifactStore;

#[derive(Clone, Debug, Eq, PartialEq, Ord, PartialOrd, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ArtifactId(pub String);

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct Artifact {
    pub id: ArtifactId,
    pub content_hash: String,
    pub skill: SkillId,
    pub agent: AgentId,
    pub topic: String,
    pub input_fingerprint: String,
    pub output_cid: Option<String>,
    pub parent_artifact_ids: Vec<ArtifactId>,
    pub schema_tags: BTreeSet<SchemaTag>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub payload: Option<PayloadRef>,
    pub created_at_unix: u64,
    pub signing_public_key: String,
    pub signature: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct ArtifactDraft {
    pub skill: SkillId,
    pub agent: AgentId,
    pub topic: String,
    pub input_fingerprint: String,
    pub output_cid: Option<String>,
    pub parent_artifact_ids: Vec<ArtifactId>,
    pub schema_tags: BTreeSet<SchemaTag>,
    #[serde(default)]
    pub payload: Option<PayloadRef>,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
struct ArtifactPayload {
    skill: SkillId,
    agent: AgentId,
    topic: String,
    input_fingerprint: String,
    output_cid: Option<String>,
    parent_artifact_ids: Vec<ArtifactId>,
    schema_tags: BTreeSet<SchemaTag>,
    payload: Option<PayloadRef>,
    created_at_unix: u64,
}

/// Reference to the canonical bytes of an artifact's payload.
///
/// `hash` is the Blake3 hex digest of the canonical payload bytes. The artifact
/// signature commits to this hash, which means tampering with the payload --
/// inline or external -- invalidates the artifact.
#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub struct PayloadRef {
    pub hash: String,
    pub encoding: PayloadEncoding,
    pub location: PayloadLocation,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub enum PayloadEncoding {
    Json,
    Cbor,
    Bytes,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
pub enum PayloadLocation {
    /// Hex-encoded canonical payload bytes embedded in the artifact.
    Inline { bytes_hex: String },
    /// External content identifier (e.g. `zg://`, `ipfs://`, `inline://...`).
    External { cid: String },
}

impl PayloadRef {
    /// Build an inline JSON payload reference from a serializable value.
    pub fn inline_json<T: Serialize>(value: &T) -> Result<Self, ArtifactError> {
        let bytes = canonical_bytes(value)?;
        Ok(Self {
            hash: blake3_hex(&bytes),
            encoding: PayloadEncoding::Json,
            location: PayloadLocation::Inline {
                bytes_hex: hex::encode(&bytes),
            },
        })
    }

    /// Build a payload reference whose bytes live behind an external CID.
    #[must_use]
    pub fn external_json<T: Serialize>(
        value: &T,
        cid: impl Into<String>,
    ) -> Result<Self, ArtifactError> {
        let bytes = canonical_bytes(value)?;
        Ok(Self {
            hash: blake3_hex(&bytes),
            encoding: PayloadEncoding::Json,
            location: PayloadLocation::External { cid: cid.into() },
        })
    }

    /// Decode inline payload bytes if they are present.
    pub fn inline_bytes(&self) -> Result<Option<Vec<u8>>, ArtifactError> {
        match &self.location {
            PayloadLocation::Inline { bytes_hex } => hex::decode(bytes_hex)
                .map(Some)
                .map_err(|error| ArtifactError::Hex(error.to_string())),
            PayloadLocation::External { .. } => Ok(None),
        }
    }

    /// Verify that arbitrary bytes match this payload reference's digest.
    pub fn verify_bytes(&self, bytes: &[u8]) -> Result<(), ArtifactError> {
        let actual = blake3_hex(bytes);
        if actual == self.hash {
            Ok(())
        } else {
            Err(ArtifactError::PayloadHashMismatch {
                expected: self.hash.clone(),
                actual,
            })
        }
    }

    /// Verify a serializable value matches this payload reference's digest.
    pub fn verify_value<T: Serialize>(&self, value: &T) -> Result<(), ArtifactError> {
        let bytes = canonical_bytes(value)?;
        self.verify_bytes(&bytes)
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
struct SignedArtifactPayload {
    id: ArtifactId,
    content_hash: String,
    payload: ArtifactPayload,
    signing_public_key: String,
}

pub struct ArtifactSigner {
    signing_key: SigningKey,
}

impl ArtifactSigner {
    #[must_use]
    pub fn from_seed(seed: [u8; 32]) -> Self {
        Self {
            signing_key: SigningKey::from_bytes(&seed),
        }
    }

    #[must_use]
    pub fn public_key_hex(&self) -> String {
        hex::encode(self.signing_key.verifying_key().to_bytes())
    }

    fn sign(&self, bytes: &[u8]) -> String {
        hex::encode(self.signing_key.sign(bytes).to_bytes())
    }
}

impl ArtifactDraft {
    pub fn seal(
        self,
        signer: &ArtifactSigner,
        created_at_unix: u64,
    ) -> Result<Artifact, ArtifactError> {
        let payload = ArtifactPayload {
            skill: self.skill,
            agent: self.agent,
            topic: self.topic,
            input_fingerprint: self.input_fingerprint,
            output_cid: self.output_cid,
            parent_artifact_ids: self.parent_artifact_ids,
            schema_tags: self.schema_tags,
            payload: self.payload,
            created_at_unix,
        };
        let payload_bytes = canonical_bytes(&payload)?;
        let content_hash = blake3_hex(&payload_bytes);
        let id = ArtifactId(format!("art_{}", &content_hash[..16]));
        let signed_payload = SignedArtifactPayload {
            id: id.clone(),
            content_hash: content_hash.clone(),
            payload: payload.clone(),
            signing_public_key: signer.public_key_hex(),
        };
        let signature = signer.sign(&canonical_bytes(&signed_payload)?);
        Ok(Artifact {
            id,
            content_hash,
            skill: payload.skill,
            agent: payload.agent,
            topic: payload.topic,
            input_fingerprint: payload.input_fingerprint,
            output_cid: payload.output_cid,
            parent_artifact_ids: payload.parent_artifact_ids,
            schema_tags: payload.schema_tags,
            payload: payload.payload,
            created_at_unix: payload.created_at_unix,
            signing_public_key: signed_payload.signing_public_key,
            signature,
        })
    }
}

impl Artifact {
    pub fn verify(&self) -> Result<(), ArtifactError> {
        let payload = self.payload();
        let payload_bytes = canonical_bytes(&payload)?;
        let expected_hash = blake3_hex(&payload_bytes);
        if self.content_hash != expected_hash {
            return Err(ArtifactError::ContentHashMismatch {
                expected: expected_hash,
                actual: self.content_hash.clone(),
            });
        }
        let expected_id = ArtifactId(format!("art_{}", &self.content_hash[..16]));
        if self.id != expected_id {
            return Err(ArtifactError::ArtifactIdMismatch {
                expected: expected_id,
                actual: self.id.clone(),
            });
        }
        let signed_payload = SignedArtifactPayload {
            id: self.id.clone(),
            content_hash: self.content_hash.clone(),
            payload,
            signing_public_key: self.signing_public_key.clone(),
        };
        verify_signature(
            &self.signing_public_key,
            &self.signature,
            &canonical_bytes(&signed_payload)?,
        )
    }

    #[must_use]
    pub fn has_parent(&self, parent: &ArtifactId) -> bool {
        self.parent_artifact_ids
            .iter()
            .any(|candidate| candidate == parent)
    }

    fn payload(&self) -> ArtifactPayload {
        ArtifactPayload {
            skill: self.skill.clone(),
            agent: self.agent.clone(),
            topic: self.topic.clone(),
            input_fingerprint: self.input_fingerprint.clone(),
            output_cid: self.output_cid.clone(),
            parent_artifact_ids: self.parent_artifact_ids.clone(),
            schema_tags: self.schema_tags.clone(),
            payload: self.payload.clone(),
            created_at_unix: self.created_at_unix,
        }
    }

    /// Verify that supplied bytes are bound to this artifact via `payload`.
    pub fn verify_payload_bytes(&self, bytes: &[u8]) -> Result<(), ArtifactError> {
        let payload_ref = self.payload.as_ref().ok_or(ArtifactError::PayloadMissing)?;
        payload_ref.verify_bytes(bytes)
    }

    /// Verify that a serializable value is bound to this artifact via `payload`.
    pub fn verify_payload_value<T: Serialize>(&self, value: &T) -> Result<(), ArtifactError> {
        let payload_ref = self.payload.as_ref().ok_or(ArtifactError::PayloadMissing)?;
        payload_ref.verify_value(value)
    }

    /// If the artifact carries an inline payload, decode and return its bytes.
    pub fn inline_payload_bytes(&self) -> Result<Option<Vec<u8>>, ArtifactError> {
        match self.payload.as_ref() {
            Some(payload_ref) => payload_ref.inline_bytes(),
            None => Ok(None),
        }
    }
}

pub trait ArtifactStore {
    fn put(&mut self, artifact: Artifact) -> Result<(), ArtifactStoreError>;
    fn get(&self, id: &ArtifactId) -> Result<Option<Artifact>, ArtifactStoreError>;
    fn children_of(&self, id: &ArtifactId) -> Result<Vec<Artifact>, ArtifactStoreError>;
    fn all(&self) -> Result<Vec<Artifact>, ArtifactStoreError>;
}

#[derive(Debug, Eq, PartialEq)]
pub enum ArtifactStoreError {
    Conflict(ArtifactId),
    Invalid(ArtifactError),
    Backend(String),
}

#[derive(Debug, Eq, PartialEq)]
pub enum ArtifactError {
    Serialization(String),
    Hex(String),
    PublicKey(String),
    Signature(String),
    ContentHashMismatch {
        expected: String,
        actual: String,
    },
    ArtifactIdMismatch {
        expected: ArtifactId,
        actual: ArtifactId,
    },
    PayloadHashMismatch {
        expected: String,
        actual: String,
    },
    PayloadMissing,
}

#[derive(Default)]
pub struct InMemoryArtifactStore {
    artifacts: BTreeMap<ArtifactId, Artifact>,
}

impl InMemoryArtifactStore {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }
}

impl ArtifactStore for InMemoryArtifactStore {
    fn put(&mut self, artifact: Artifact) -> Result<(), ArtifactStoreError> {
        artifact.verify().map_err(ArtifactStoreError::Invalid)?;
        if self.artifacts.contains_key(&artifact.id) {
            return Err(ArtifactStoreError::Conflict(artifact.id));
        }
        self.artifacts.insert(artifact.id.clone(), artifact);
        Ok(())
    }

    fn get(&self, id: &ArtifactId) -> Result<Option<Artifact>, ArtifactStoreError> {
        Ok(self.artifacts.get(id).cloned())
    }

    fn children_of(&self, id: &ArtifactId) -> Result<Vec<Artifact>, ArtifactStoreError> {
        Ok(self
            .artifacts
            .values()
            .filter(|artifact| artifact.has_parent(id))
            .cloned()
            .collect())
    }

    fn all(&self) -> Result<Vec<Artifact>, ArtifactStoreError> {
        Ok(self.artifacts.values().cloned().collect())
    }
}

pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>, ArtifactError> {
    serde_json::to_vec(value).map_err(|error| ArtifactError::Serialization(error.to_string()))
}

#[must_use]
pub fn blake3_hex(bytes: &[u8]) -> String {
    blake3::hash(bytes).to_hex().to_string()
}

#[must_use]
pub fn deterministic_placeholder_hash(parts: &[&str]) -> String {
    blake3_hex(parts.join("|").as_bytes())
}

fn verify_signature(
    public_key_hex: &str,
    signature_hex: &str,
    bytes: &[u8],
) -> Result<(), ArtifactError> {
    let public_key_bytes =
        hex::decode(public_key_hex).map_err(|error| ArtifactError::Hex(error.to_string()))?;
    let public_key_bytes: [u8; 32] = public_key_bytes
        .try_into()
        .map_err(|_| ArtifactError::PublicKey("expected 32-byte Ed25519 public key".to_string()))?;
    let signature_bytes =
        hex::decode(signature_hex).map_err(|error| ArtifactError::Hex(error.to_string()))?;
    let signature_bytes: [u8; 64] = signature_bytes
        .try_into()
        .map_err(|_| ArtifactError::Signature("expected 64-byte Ed25519 signature".to_string()))?;
    let verifying_key = VerifyingKey::from_bytes(&public_key_bytes)
        .map_err(|error| ArtifactError::PublicKey(error.to_string()))?;
    let signature = Signature::from_bytes(&signature_bytes);
    verifying_key
        .verify(bytes, &signature)
        .map_err(|error| ArtifactError::Signature(error.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn signer() -> ArtifactSigner {
        ArtifactSigner::from_seed([7; 32])
    }

    fn draft(parent: Vec<ArtifactId>) -> ArtifactDraft {
        ArtifactDraft {
            skill: SkillId("chem.dft.pyscf.b3lyp.v1".to_string()),
            agent: AgentId("worker-1.dft.eth".to_string()),
            topic: "demo molecule".to_string(),
            input_fingerprint: "input:demo".to_string(),
            output_cid: Some("zg://demo-output".to_string()),
            parent_artifact_ids: parent,
            schema_tags: BTreeSet::from([SchemaTag("chem.dft.result".to_string())]),
            payload: None,
        }
    }

    #[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
    struct DemoPayload {
        molecule: String,
        energy_hartree: i64,
    }

    fn payload_draft(parent: Vec<ArtifactId>, payload: PayloadRef) -> ArtifactDraft {
        ArtifactDraft {
            skill: SkillId("chem.dft.pyscf.b3lyp.v1".to_string()),
            agent: AgentId("worker-1.dft.eth".to_string()),
            topic: "payload-bound demo".to_string(),
            input_fingerprint: "input:demo-payload".to_string(),
            output_cid: None,
            parent_artifact_ids: parent,
            schema_tags: BTreeSet::from([SchemaTag("chem.dft.result".to_string())]),
            payload: Some(payload),
        }
    }

    #[test]
    fn sealed_artifact_verifies() {
        let artifact = draft(Vec::new()).seal(&signer(), 1).expect("seal");
        artifact.verify().expect("valid signature");
    }

    #[test]
    fn tampered_artifact_fails_verification() {
        let mut artifact = draft(Vec::new()).seal(&signer(), 1).expect("seal");
        artifact.topic = "tampered".to_string();
        assert!(matches!(
            artifact.verify(),
            Err(ArtifactError::ContentHashMismatch { .. })
        ));
    }

    #[test]
    fn payload_bound_artifact_round_trips() {
        let value = DemoPayload {
            molecule: "H2O".to_string(),
            energy_hartree: -76,
        };
        let payload_ref = PayloadRef::inline_json(&value).expect("inline payload");
        let artifact = payload_draft(Vec::new(), payload_ref.clone())
            .seal(&signer(), 5)
            .expect("seal");
        artifact.verify().expect("signature");
        artifact
            .verify_payload_value(&value)
            .expect("payload digest matches the original value");
        let bytes = artifact
            .inline_payload_bytes()
            .expect("decode inline")
            .expect("inline payload present");
        let recovered: DemoPayload = serde_json::from_slice(&bytes).expect("decode");
        assert_eq!(recovered, value);
    }

    #[test]
    fn tampered_inline_payload_breaks_signature() {
        let value = DemoPayload {
            molecule: "H2O".to_string(),
            energy_hartree: -76,
        };
        let payload_ref = PayloadRef::inline_json(&value).expect("inline payload");
        let mut artifact = payload_draft(Vec::new(), payload_ref)
            .seal(&signer(), 6)
            .expect("seal");
        // Replace the inline bytes with a different but valid JSON payload.
        if let Some(PayloadRef {
            location: PayloadLocation::Inline { bytes_hex },
            ..
        }) = artifact.payload.as_mut()
        {
            let attacker_value = DemoPayload {
                molecule: "D2O".to_string(),
                energy_hartree: -77,
            };
            let attacker_bytes = canonical_bytes(&attacker_value).expect("canonical");
            *bytes_hex = hex::encode(&attacker_bytes);
        } else {
            panic!("expected inline payload in tampered artifact");
        }
        assert!(matches!(
            artifact.verify(),
            Err(ArtifactError::ContentHashMismatch { .. })
        ));
    }

    #[test]
    fn payload_value_mismatch_is_rejected_against_artifact() {
        let value = DemoPayload {
            molecule: "H2O".to_string(),
            energy_hartree: -76,
        };
        let payload_ref = PayloadRef::external_json(&value, "zg://demo/h2o").expect("external");
        let artifact = payload_draft(Vec::new(), payload_ref)
            .seal(&signer(), 7)
            .expect("seal");
        let attacker_value = DemoPayload {
            molecule: "H2O".to_string(),
            energy_hartree: 0,
        };
        assert!(matches!(
            artifact.verify_payload_value(&attacker_value),
            Err(ArtifactError::PayloadHashMismatch { .. })
        ));
    }

    #[test]
    fn store_indexes_parent_child_lineage() {
        let signer = signer();
        let parent = draft(Vec::new()).seal(&signer, 1).expect("parent");
        let child = draft(vec![parent.id.clone()])
            .seal(&signer, 2)
            .expect("child");
        let mut store = InMemoryArtifactStore::new();
        store.put(parent.clone()).expect("put parent");
        store.put(child.clone()).expect("put child");
        let children = store.children_of(&parent.id).expect("children");
        assert_eq!(children, vec![child]);
    }
}
