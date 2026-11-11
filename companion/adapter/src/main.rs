use chimiaclaw_artifact::{Artifact,ArtifactDraft,ArtifactSigner,PayloadRef};
use chimiaclaw_node::{NodeProfile,NodeRuntime};
use chimiaclaw_schema::{AgentId,Capability,SchemaTag,SkillId};
use chimiaclaw_skill::{Skill,SkillCtx,SkillError};
use serde_json::{json,Value};
use sha2::{Digest,Sha256};
use std::{collections::BTreeSet,fs,io::Read,path::{Path,PathBuf},time::{SystemTime,UNIX_EPOCH}};
const MANIFEST: &str=include_str!("../../fixtures/pbso4/manifest.json");
fn err(e:impl std::fmt::Debug)->String{format!("{e:?}")}
fn sha(b:&[u8])->String{format!("{:x}",Sha256::digest(b))}
fn read_regular(path:&Path)->Result<Vec<u8>,String>{let m=fs::symlink_metadata(path).map_err(err)?;if !m.file_type().is_file(){return Err(format!("not a regular file: {}",path.display()))}fs::read(path).map_err(err)}
fn check_fixture(root:&Path)->Result<Value,String>{
 let dir=root.join("fixtures/pbso4");if fs::symlink_metadata(&dir).map_err(err)?.file_type().is_symlink(){return Err("symlink fixture directory".into())}
 let manifest=read_regular(&dir.join("manifest.json"))?;if manifest!=MANIFEST.as_bytes(){return Err("fixture manifest differs from compiled commitment".into())}
 let m:Value=serde_json::from_str(MANIFEST).map_err(err)?;let files=m["files_sha256"].as_object().ok_or("file map")?;
 for (name,digest) in files{if name.contains('/')||name.contains("..") {return Err("unsafe manifest path".into())}if sha(&read_regular(&dir.join(name))?)!=digest.as_str().ok_or("digest")?{return Err(format!("source SHA-256 mismatch: {name}"))}}
 for ent in fs::read_dir(&dir).map_err(err)?{let ent=ent.map_err(err)?;let name=ent.file_name().to_string_lossy().to_string();if name!="manifest.json"&&!files.contains_key(&name){return Err(format!("unlisted fixture file: {name}"))}}
 let metrics:Value=serde_json::from_slice(&read_regular(&dir.join("native-metrics.json"))?).map_err(err)?;
 let historical:Value=serde_json::from_slice(&read_regular(&dir.join("historical-receipt.json"))?).map_err(err)?;
 if historical["status"]!="completed"||historical["completed_steps"]!=8||historical["worker_exit_code"]!=0||historical["cleanup_confirmed"]!=true||historical["original_frozen_config_sha256"]!=historical["recorded_config_sha256"]||historical["sanitized_native_metrics_sha256"]!=m["files_sha256"]["native-metrics.json"]||historical["sanitized_case_sha256"]!=m["files_sha256"]["case.json"]||historical["included_pattern_sha256"]!=m["files_sha256"]["refinement_pattern.csv"]||historical["original_pattern_sha256"]!=historical["included_pattern_sha256"]||historical["metrics_semantically_equal_checked"]!=true{return Err("historical receipt binding failed".into())}
 for name in ["PBSO4.XRA","INST_XRY.PRM","PbSO4-Wyckoff.cif"]{if historical["source_inputs_sha256"][name]!=m["files_sha256"][name]{return Err("historical input binding failed".into())}}
 let rwp=metrics["metrics"]["histograms"][0]["wR"].as_f64().ok_or("missing native wR")?;if (rwp-32.476329298163684).abs()>1e-12{return Err("unexpected native metric".into())}
 let csv=String::from_utf8(read_regular(&dir.join("refinement_pattern.csv"))?).map_err(err)?;
 let mut count=0;let mut fit=0;let mut last=f64::NEG_INFINITY;
 for line in csv.lines().skip(1){let v:Vec<f64>=line.split(',').map(str::parse).collect::<Result<_,_>>().map_err(err)?;if v.len()!=4||v.iter().any(|x|!x.is_finite())||v[0]<=last{return Err("invalid native profile rows".into())}if (v[1]-v[2]-v[3]).abs()>0.000002{return Err("residual parity mismatch".into())}last=v[0];count+=1;if (16.0..=110.0).contains(&v[0]){fit+=1}}
 if count!=6000||fit!=3761{return Err(format!("unexpected profile dimensions {count}/{fit}"))}
 Ok(json!({"case_id":"pbso4-gsas-tutorial-xray-v1","mode":"VERIFIED_REPLAY_OF_HISTORICAL_NATIVE_EXECUTION","native_execution_date":"2026-09-13","historical_receipt_sha256":m["files_sha256"]["historical-receipt.json"],"fresh_native_refinement":false,"native_Rwp_percent":rwp,"fit_limits_two_theta_deg":[16,110],"fit_observations":fit,"exported_points":count,"exported_range_two_theta_deg":[10,159.975],"source_sha256":m["files_sha256"],"source_manifest_sha256":sha(MANIFEST.as_bytes()),"result_status":"SOFTWARE_INTEGRATION_VERIFIED_SCIENTIFIC_REVIEW_PENDING","warnings":["Poor residual remains visible; no physical-model validation or structure selection.","Starting CIF is not a truth label; supplied instrument approximation fixed.","Rwp applies only to 16–110 degrees / 3761 observations, not all 6000 exported points.","Configured cycles per stage: 3; last stage native listing reports 4. No actual three-cycle claim.","Signatures verify against a local ephemeral demonstration key; no external identity attestation."]}))
}
struct PxrdReplaySkill{root:PathBuf}
impl Skill for PxrdReplaySkill{
 fn id(&self)->SkillId{SkillId("science.pxrd.verified_replay.v1".into())}
 fn capabilities(&self)->Vec<Capability>{vec![]}
 fn consumes_tags(&self)->Vec<SchemaTag>{vec![SchemaTag("science.pxrd.request.v1".into())]}
 fn produces_tags(&self)->Vec<SchemaTag>{vec![SchemaTag("science.pxrd.replay_result.v1".into())]}
 fn invoke(&self,ctx:&SkillCtx,parents:&[Artifact])->Result<ArtifactDraft,SkillError>{
  let p=parents.first().ok_or_else(||SkillError::InvalidInput("missing signed request".into()))?;
  verify_artifact(p,&p.signing_public_key).map_err(SkillError::InvalidInput)?;
  let request:Value=serde_json::from_slice(&p.inline_payload_bytes().map_err(|e|SkillError::InvalidInput(err(e)))?.ok_or_else(||SkillError::InvalidInput("request payload missing".into()))?).map_err(|e|SkillError::InvalidInput(err(e)))?;
  if request["operation"]!="verify_recorded_native_result"||request["fixture_manifest_sha256"]!=sha(MANIFEST.as_bytes()){return Err(SkillError::InvalidInput("request not bound to this replay fixture".into()))}
  let result=check_fixture(&self.root).map_err(SkillError::Execution)?;
  Ok(ArtifactDraft{skill:self.id(),agent:ctx.agent.clone(),topic:"PbSO4: verified native replay, scientific review pending".into(),input_fingerprint:p.content_hash.clone(),output_cid:None,parent_artifact_ids:vec![p.id.clone()],schema_tags:BTreeSet::from([self.produces_tags()[0].clone()]),payload:Some(PayloadRef::inline_json(&result).map_err(|e|SkillError::Execution(err(e)))?)})
 }
}
fn verify_artifact(a:&Artifact,expected_key:&str)->Result<(),String>{if a.signing_public_key!=expected_key{return Err("signing key differs from recorded local demo key".into())}a.verify().map_err(err)?;let b=a.inline_payload_bytes().map_err(err)?.ok_or("inline payload missing")?;a.verify_payload_bytes(&b).map_err(err)}
fn write_json(p:&Path,v:&Value)->Result<(),String>{fs::write(p,serde_json::to_vec_pretty(v).map_err(err)?).map_err(err)}
fn now()->u64{SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs()}
fn run(root:&Path,verify_only:bool)->Result<Value,String>{
 let scientific=check_fixture(root)?;
 let csv=String::from_utf8(read_regular(&root.join("fixtures/pbso4/refinement_pattern.csv"))?).map_err(err)?;
 let profile:Vec<Vec<f64>>=csv.lines().skip(1).map(|line|line.split(',').map(str::parse).collect::<Result<Vec<f64>,_>>()).collect::<Result<_,_>>().map_err(err)?;
 fs::write(root.join("public/profile.js"),format!("window.PROFILE = {};\n",serde_json::to_string(&profile).map_err(err)?)).map_err(err)?;
 let out=root.join("run");fs::create_dir_all(&out).map_err(err)?;
 let mut seed=[0;32];fs::File::open("/dev/urandom").map_err(err)?.read_exact(&mut seed).map_err(err)?;
 let signer=ArtifactSigner::from_seed(seed);seed.fill(0);
 let keypath=out.join("demo-public-key.json");let store=out.join("artifact-store");
 let mut runtime=NodeRuntime::open(NodeProfile{agent:AgentId("pxrd-replay.local-demo".into()),signer,store_dir:store}).map_err(err)?;
 let existing=runtime.all_artifacts().map_err(err)?;
 let key=if existing.is_empty(){
  if verify_only{return Err("no existing run to verify".into())}
  let reqsign=ArtifactSigner::from_seed({let mut b=[0;32];fs::File::open("/dev/urandom").map_err(err)?.read_exact(&mut b).map_err(err)?;b});
  let pk=reqsign.public_key_hex();
  let req=json!({"question":"What does this measured diffraction calculation establish?","operation":"verify_recorded_native_result","fixture_manifest_sha256":sha(MANIFEST.as_bytes()),"requested_interpretation":"Expose source identity, recorded native result, and unresolved scientific limitations."});
  let parent=ArtifactDraft{skill:SkillId("science.pxrd.request.v1".into()),agent:AgentId("researcher.local-demo".into()),topic:"Assess public PbSO4 fixture".into(),input_fingerprint:sha(MANIFEST.as_bytes()),output_cid:None,parent_artifact_ids:vec![],schema_tags:BTreeSet::from([SchemaTag("science.pxrd.request.v1".into())]),payload:Some(PayloadRef::inline_json(&req).map_err(err)?)}.seal(&reqsign,now()).map_err(err)?;
  runtime.put_artifact(parent).map_err(err)?;
  // NodeRuntime uses its own independent ephemeral signer, whose key is read from its produced child.
  write_json(&keypath,&json!({"request_public_key":pk,"identity":"local ephemeral demonstration signers; not externally attested"}))?;pk
 }else{let k:Value=serde_json::from_slice(&read_regular(&keypath)?).map_err(err)?;k["request_public_key"].as_str().ok_or("missing key")?.to_string()};
 let mut keyrecord:Value=serde_json::from_slice(&read_regular(&keypath)?).map_err(err)?;
 for a in &existing{let expected=if a.parent_artifact_ids.is_empty(){&key}else{keyrecord["worker_public_key"].as_str().ok_or("worker key missing")?};verify_artifact(a,expected)?;}
 runtime.register_skill(Box::new(PxrdReplaySkill{root:root.to_path_buf()}));
 let first=if verify_only{None}else{Some(runtime.run_once(now()).map_err(err)?)};
 if let Some(r)=&first{if r.invocations.iter().any(|x|!x.failures.is_empty()){return Err(format!("skill failures: {:?}",r.invocations))}}
 let arts=runtime.all_artifacts().map_err(err)?;if arts.len()!=2{return Err(format!("expected request and result, got {}",arts.len()))}
 let parent=arts.iter().find(|a|a.parent_artifact_ids.is_empty()).ok_or("parent missing")?;
 let child=arts.iter().find(|a|!a.parent_artifact_ids.is_empty()).ok_or("child missing")?;
 if child.parent_artifact_ids!=vec![parent.id.clone()]||child.input_fingerprint!=parent.content_hash{return Err("lineage mismatch".into())}
 if keyrecord["worker_public_key"].is_null(){if verify_only{return Err("worker key missing".into())}keyrecord["worker_public_key"]=json!(child.signing_public_key);write_json(&keypath,&keyrecord)?;}
 verify_artifact(parent,&key)?;verify_artifact(child,keyrecord["worker_public_key"].as_str().ok_or("key")?)?;
 let child_payload:Value=serde_json::from_slice(&child.inline_payload_bytes().map_err(err)?.ok_or("payload")?).map_err(err)?;
 if child_payload!=scientific{return Err("signed result does not match current verified fixture".into())}
 let second=runtime.run_once(now()).map_err(err)?;
 let invocation=&second.invocations[0];if !invocation.produced_children.is_empty()||invocation.skipped_existing!=vec![child.id.clone()]||!invocation.failures.is_empty(){return Err("idempotency failed".into())}
 let mut tampered=child.clone();tampered.topic.push_str(" altered");let envelope_rejected=verify_artifact(&tampered,&child.signing_public_key).is_err();
 let mut payload_tampered=child.clone();payload_tampered.payload=Some(PayloadRef::inline_json(&json!({"native_Rwp_percent":0})).map_err(err)?);let payload_rejected=verify_artifact(&payload_tampered,&child.signing_public_key).is_err();
 let mut wrong_key=child.clone();wrong_key.signing_public_key=parent.signing_public_key.clone();let key_rejected=verify_artifact(&wrong_key,&child.signing_public_key).is_err();
 if !envelope_rejected||!payload_rejected||!key_rejected{return Err("tamper test failed".into())}
 let views:Vec<Value>=arts.iter().map(|a|json!({"artifact":a,"decoded_payload":serde_json::from_slice::<Value>(&a.inline_payload_bytes().unwrap().unwrap()).unwrap(),"signature_verified":true,"payload_verified":true})).collect();
 let report=json!({"status":"PASS_VERIFIED_REPLAY","executed_at_unix":now(),"runtime":"real OpenAgents NodeRuntime::run_once + PxrdReplaySkill::invoke + FileArtifactStore","first_pass":first.map(|r|r.invocations),"second_pass":second.invocations,"signing_key_scope":keyrecord,"tests":{"envelope_tamper_rejected":envelope_rejected,"payload_tamper_rejected":payload_rejected,"key_substitution_rejected":key_rejected,"second_run_idempotent":true,"fixture_hashes_checked":true},"science":scientific,"artifacts":views});
 let reportpath=out.join("report.json");
 if !reportpath.exists(){if verify_only{return Err("initial execution receipt missing".into())}write_json(&reportpath,&report)?;}
 let original:Value=serde_json::from_slice(&read_regular(&reportpath)?).map_err(err)?;
 if original["artifacts"]!=report["artifacts"]||original["science"]!=report["science"]||original["first_pass"].is_null(){return Err("initial execution receipt differs from verified artifacts or lacks invocation".into())}
 write_json(&out.join("verification.json"),&json!({"status":"PASS","verified_at_unix":now(),"initial_report_sha256":sha(&read_regular(&reportpath)?),"tests":report["tests"],"second_pass":report["second_pass"]}))?;
 fs::write(root.join("public/data.js"),format!("window.DEMO = {};\n",serde_json::to_string(&original).map_err(err)?)).map_err(err)?;
 Ok(report)
}
fn main(){let verify=std::env::args().any(|x|x=="--verify");let root=std::env::current_dir().expect("cwd");match run(&root,verify){Ok(r)=>println!("{}",serde_json::to_string_pretty(&json!({"status":r["status"],"tests":r["tests"],"native_Rwp_percent":r["science"]["native_Rwp_percent"],"mode":r["science"]["mode"]})).unwrap()),Err(e)=>{eprintln!("REJECTED: {e}");std::process::exit(1)}}}
#[cfg(test)]mod tests{
 use super::*;
 fn copy_fixture(tag:&str)->PathBuf{let dir=std::env::temp_dir().join(format!("pxrd-replay-{tag}-{}-{}",std::process::id(),now()));let dst=dir.join("fixtures/pbso4");fs::create_dir_all(&dst).unwrap();let src=Path::new(env!("CARGO_MANIFEST_DIR")).join("../fixtures/pbso4");for e in fs::read_dir(src).unwrap(){let e=e.unwrap();fs::copy(e.path(),dst.join(e.file_name())).unwrap();}dir}
 #[test]fn production_fixture_accepts(){let p=Path::new(env!("CARGO_MANIFEST_DIR")).join("..");assert!(check_fixture(&p).is_ok());}
 #[test]fn modified_source_rejects(){let p=copy_fixture("source");fs::write(p.join("fixtures/pbso4/PBSO4.XRA"),b"changed").unwrap();assert!(check_fixture(&p).unwrap_err().contains("SHA-256 mismatch"));}
 #[test]fn modified_manifest_rejects(){let p=copy_fixture("manifest");fs::write(p.join("fixtures/pbso4/manifest.json"),b"{}").unwrap();assert!(check_fixture(&p).unwrap_err().contains("compiled commitment"));}
 #[test]fn extra_file_rejects(){let p=copy_fixture("extra");fs::write(p.join("fixtures/pbso4/extra"),b"x").unwrap();assert!(check_fixture(&p).unwrap_err().contains("unlisted"));}
 #[cfg(unix)]#[test]fn symlink_source_rejects(){use std::os::unix::fs::symlink;let p=copy_fixture("link");let f=p.join("fixtures/pbso4/PBSO4.XRA");fs::rename(&f,p.join("saved")).unwrap();symlink(p.join("saved"),f).unwrap();assert!(check_fixture(&p).unwrap_err().contains("not a regular file"));}
}
