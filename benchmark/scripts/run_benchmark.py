"""Independent finite controls and frozen-code VT07 geometry transfer. No fitting."""
from pathlib import Path
import argparse, cmath, hashlib, itertools, json, math, platform, sys, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import numpy as np
import gemmi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from crystalbench import (Site, SourceModel, ExclusionEdge, ContractError, expand,
                          structure_factors, write_cif, cell_from_parameters)

TRANSFORMS = [np.eye(3, dtype=int), np.diag([2,3,1]),
              np.array([[2,1,0],[0,2,0],[0,0,1]]),
              np.array([[1,1,0],[0,1,1],[0,0,1]]),
              np.array([[0,1,0],[-2,0,0],[0,0,1]]),
              np.array([[2,-1,1],[0,1,0],[0,0,2]])]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def freeze():
    paths = sorted((ROOT/'src/crystalbench').glob('*.py')) + sorted((ROOT/'protocol').glob('*.md'))
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}

def inverse_fraction(H):
    """Independent rational Gauss-Jordan inversion, not the core's adjugate code."""
    rows = [[Fraction(int(H[i,j])) for j in range(3)] +
            [Fraction(int(i==j)) for j in range(3)] for i in range(3)]
    for c in range(3):
        p = next(r for r in range(c,3) if rows[r][c])
        rows[c], rows[p] = rows[p], rows[c]
        pivot=rows[c][c]; rows[c]=[x/pivot for x in rows[c]]
        for r in range(3):
            if r != c:
                v=rows[r][c]; rows[r]=[a-v*b for a,b in zip(rows[r],rows[c])]
    return [r[3:] for r in rows]

def reference_cosets(H):
    inv=inverse_fraction(H); det=round(np.linalg.det(H)); representatives={}
    for t in itertools.product(range(det), repeat=3):
        residue=tuple(sum(t[i]*inv[i][j] for i in range(3)) % 1 for j in range(3))
        representatives.setdefault(residue,t)
    assert len(representatives)==det
    return list(representatives.values()),inv

def scalar_reference(sites, hkls, factors):
    values=[]
    for k,h in enumerate(hkls):
        terms=[]
        for s in sites:
            f=factors[s.species]
            f=f if np.ndim(f)==0 else f[k]
            phase=2*math.pi*sum(float(a)*float(b) for a,b in zip(h,s.frac))
            terms.append(s.occupancy*complex(f)*cmath.exp(1j*phase))
        values.append(complex(math.fsum(t.real for t in terms),math.fsum(t.imag for t in terms)))
    return np.asarray(values)

class Audit:
    def __init__(self): self.checks=[]
    def check(self,name,ok,**detail):
        self.checks.append(dict(name=name,status='PASS' if bool(ok) else 'FAIL',**detail))
    def amplitude(self,name,a,b,model,h,factors,H=None,extra=None):
        h=np.asarray(h); n=len(model.sites)
        if not len(h) and name.endswith('satellite_cancellation'):
            self.checks.append(dict(name=name,status='NOT_APPLICABLE',vectors=0,reason='determinant-one transform has no extra satellites'))
            return np.array([])
        m=np.zeros(len(h))
        for s in model.sites: m += np.abs(s.occupancy*np.asarray(factors[s.species]))
        kappa=1 if H is None else float(np.linalg.cond(H))
        K=128*n+64*(1+2*np.pi*np.sum(abs(h),axis=1))*(1+kappa)
        eps=np.finfo(float).eps
        tau=2*K*eps/(1-K*eps)*np.maximum(1,m)
        if extra is not None: tau+=extra
        error=abs(a-b)
        self.check(name,np.all(K*eps<1e-6) and np.all(error<=tau),
                   vectors=len(h),max_abs_error=float(max(error,default=0)),
                   max_error_budget_ratio=float(max(error/tau,default=0)),
                   max_amplitude_budget=float(max(tau,default=0)))
        return tau

def grid(n): return np.array(list(itertools.product(range(-n,n+1),repeat=3)))

def cif_roundtrip(model,out,audit,name):
    path=out/(name+'.cif');write_cif(model,path)
    parsed=gemmi.read_small_structure(str(path)); block=gemmi.cif.read(str(path)).sole_block()
    originals={s.label:s for s in model.sites}
    delta=[];same=len(parsed.sites)==len(originals)
    for s in parsed.sites:
        if s.label not in originals:same=False;continue
        original=originals[s.label]
        delta.append(max(abs((np.asarray(tuple(s.fract))-original.frac+.5)%1-.5)))
        same &= s.element.name==original.species and abs(s.occ-original.occupancy)<5e-13
    # CIF carries a metric, not arbitrary Cartesian orientation.
    rows=np.array(model.cell)
    parsed_rows=np.array(parsed.cell.orth.mat).T
    metric_error=float(np.max(abs(rows@rows.T-parsed_rows@parsed_rows.T)))
    unknown=list(block.find_values('_atom_site_U_iso_or_equiv'))
    same &= all((u=='?')== (s.u_iso is None) for u,s in zip(unknown,model.sites))
    audit.check(name,same and max(delta,default=0)<=5.1e-13 and metric_error<1e-10,
                sites=len(parsed.sites),max_wrapped_coordinate_error=float(max(delta,default=0)),
                metric_max_abs_error=metric_error,unknown_adps_preserved=True)

def run_synthetic(out,audit):
    source=SourceModel(((4,0,0),(1,5,0),(.5,.25,6)),
        (Site('C1','C',(1/7,2/9,1/5),.5),Site('O1','O',(2/5,1/3,3/7),.75),
         Site('N1','N',(0,1/8,2/3),1)),source_id='synthetic-rational-oblique-v1')
    factors={'C':1+.2j,'O':2-.3j,'N':.7+.1j}; gp=grid(3); gs=grid(4)
    original=scalar_reference(source.sites,gp,factors)
    audit.amplitude('synthetic_parent_direct_sum',structure_factors(source,gp,factors,adp_mode='none'),original,source,gp,factors)
    for no,H in enumerate(TRANSFORMS):
        model=expand(source,H); det=round(np.linalg.det(H)); reps,inv=reference_cosets(H)
        # Reference positions use a separate rational inverse and independent cosets.
        ref_sites=[]
        for k,t in enumerate(reps):
            for s in source.sites:
                frac=[float(sum((Fraction(str(s.frac[i]))+t[i])*inv[i][j] for i in range(3))%1) for j in range(3)]
                ref_sites.append(Site(f'{s.label}_r{k}',s.species,tuple(frac),s.occupancy))
        actual=structure_factors(model,gs,factors,adp_mode='none')
        expected=scalar_reference(ref_sites,gs,factors)
        audit.amplitude(f'H{no}_independent_cosets_amplitudes',actual,expected,model,gs,factors,H)
        embedded=gp@H.T
        audit.amplitude(f'H{no}_repeat_identity',structure_factors(model,embedded,factors,adp_mode='none'),det*original,model,embedded,factors,H)
        satellite=np.array([not all(sum(Fraction(int(h[j]))*inv[i][j] for j in range(3)).denominator==1 for i in range(3)) for h in gs])
        audit.amplitude(f'H{no}_satellite_cancellation',actual[satellite],np.zeros(sum(satellite),complex),model,gs[satellite],factors,H)
        audit.check(f'H{no}_composition',all(abs(model.composition[k]-det*v)<1e-13 for k,v in source.composition.items()),determinant=det,site_count=len(model.sites))
        cif_roundtrip(model,out,audit,f'H{no}_cif_roundtrip')
    shift=np.array([1/11,-2/7,3/13])
    shifted=SourceModel(source.cell,tuple(Site(s.label,s.species,tuple(np.array(s.frac)+shift),s.occupancy) for s in source.sites))
    fs=structure_factors(shifted,gp,factors,adp_mode='none')
    audit.amplitude('origin_shift_phase',fs,original*np.exp(2j*np.pi*gp@shift),shifted,gp,factors)

    ring=SourceModel(((1,0,0),(0,1,0),(0,0,1)),(Site('C1','C',(0,0,0),1/3),),source_id='periodic-12-ring-v1')
    H=np.diag([12,1,1]); base=expand(ring,H); hm=np.array([[h,0,0] for h in range(12)])
    fixtures={'A':{0,1,2,3},'B':{0,2,4,6},'C':{0,1,4,6},'D':{0,1,3,7}}
    results={}; ring_f={}; ring_tau={}
    for name,occupied in fixtures.items():
        bits=[[int(t[0]%12 in occupied)] for t in base.translations]
        model=expand(ring,H,occupancies=bits,exact_counts={'C':4})
        f=structure_factors(model,hm,{'C':1},adp_mode='none')
        ref=np.array([sum(cmath.exp(2j*math.pi*h*j/12) for j in sorted(occupied)) for h in range(12)])
        ring_tau[name]=audit.amplitude('ring_'+name+'_independent',f,ref,model,hm,{'C':1},H)
        ring_f[name]=f
        audit.check('ring_'+name+'_exact_mean',sum(x[0] for x in bits)==4 and Fraction(sum(x[0] for x in bits),12)==Fraction(1,3))
        results[name]=abs(f)**2
    def autocorr(v):return tuple(sum(int(i in v)*int((i+d)%12 in v) for i in range(12)) for d in range(12))
    def orbit(v):return min(tuple(sorted((sign*i+shift)%12 for i in v)) for sign in [-1,1] for shift in range(12))
    classes=defaultdict(set)
    for seq in itertools.combinations(range(12),4):classes[autocorr(set(seq))].add(orbit(seq))
    audit.check('homometric_integer_certificate',autocorr(fixtures['C'])==autocorr(fixtures['D']) and orbit(fixtures['C'])!=orbit(fixtures['D']),patterns_enumerated=495,autocorrelation_classes=len(classes),ambiguous_classes=sum(len(v)>1 for v in classes.values()),autocorrelation_C=list(autocorr(fixtures['C'])))
    tau=ring_tau['C']+ring_tau['D']; intensity_budget=2*abs(ring_f['D'])*tau+tau**2
    audit.check('homometric_intensity',np.all(abs(results['C']-results['D'])<=intensity_budget),max_abs_error=float(np.max(abs(results['C']-results['D']))))
    tau_ab=ring_tau['A']+ring_tau['B']; distinguishable=abs(results['A']-results['B'])>2*abs(ring_f['B'])*tau_ab+tau_ab**2
    audit.check('same_mean_different_intensity',np.any(distinguishable),distinct_modes=int(np.count_nonzero(distinguishable)),max_intensity_difference=float(np.max(abs(results['A']-results['B']))))
    np.savetxt(out/'ring_intensities.csv',np.column_stack([np.arange(12)]+list(results.values())),delimiter=',',header='discrete_h,A,B,C,D',comments='')
    edge=ExclusionEdge(0,0,(1,0,0),'synthetic nearest-cell ring rule; supplied explicitly')
    for name,occupied,expected in [('alternating',set(range(0,12,2)),True),('wrapped_pair',{0,11},False),('adjacent_pair',{0,1},False)]:
        try:expand(ring,H,occupancies=[[int(t[0]%12 in occupied)] for t in base.translations],exclusions=[edge]);accepted=True
        except ContractError:accepted=False
        audit.check('exclusion_'+name,accepted==expected)
    return {'transform_count':len(TRANSFORMS),'ring_fixture_count':4,'independence':'rational Gauss-Jordan cosets, scalar cmath sums, exhaustive integer autocorrelations; no core quotient/reference calls'}

def factors_for(model,h):
    g=np.asarray(h)@np.linalg.inv(np.array(model.cell)).T
    s2=np.sum(g*g,axis=1)/4
    return {species:np.array([gemmi.Element(species).it92.calculate_sf(float(s)) for s in s2]) for species in model.composition}

def run_external(out,audit):
    cif=ROOT/'data/vt07/source.cif'
    assert sha(cif)=='093c4d1121c232bc9bdda7340738138b0622c0c6804fa3ad28facde29fe324f4'
    original=gemmi.read_small_structure(str(cif))
    all_sites=original.get_all_unit_cell_sites()
    sites=tuple(Site(f'{s.label}_{i}',s.element.name,tuple(s.fract),s.occ,None) for i,s in enumerate(all_sites))
    source=SourceModel(cell_from_parameters(*original.cell.parameters),sites,
                       nominal_composition={'Ca':2.15,'Sr':.85,'Ti':2,'O':7},
                       source_id='doi:10.6084/m9.figshare.12446306.v1#300K-A21am')
    block=gemmi.cif.read(str(cif)).sole_block(); literal=defaultdict(Fraction)
    for symbol,multiplicity,occupancy in zip(block.find_values('_atom_site_type_symbol'),block.find_values('_atom_site_symmetry_multiplicity'),block.find_values('_atom_site_occupancy')):
        literal[symbol]+=int(multiplicity)*Fraction(occupancy)
    audit.check('VT07_literal_multiplicity_composition',set(literal)==set(source.composition) and all(abs(float(v)-source.composition[k])<1e-12 for k,v in literal.items()),literal_counts={k:str(v) for k,v in literal.items()},site_species_records=len(sites),weighted_atom_count=float(sum(literal.values())))
    (out/'vt07_source_contract.json').write_text(json.dumps(source.to_dict(),indent=2)+'\n')
    hp=grid(6); factors=factors_for(source,hp)
    calc=structure_factors(source,hp,factors,adp_mode='none')
    scalar=scalar_reference(source.sites,hp,factors)
    audit.amplitude('VT07_scalar_reference',calc,scalar,source,hp,factors)
    # Gemmi documents this occupancy conversion for special-position SF sums.
    original.change_occupancies_to_crystallographic()
    engine=gemmi.StructureFactorCalculatorX(original.cell)
    library=np.array([engine.calculate_sf_from_small_structure(original,list(map(int,h))) for h in hp])
    audit.amplitude('VT07_Gemmi_independent_structure_factors',calc,library,source,hp,factors)
    np.savez_compressed(out/'vt07_factors.npz',hkl=hp,core=calc,scalar=scalar,gemmi=library)
    np.savetxt(out/'vt07_factor_errors.csv',np.column_stack([hp,abs(calc-library),abs(library)]),delimiter=',',header='h,k,l,absolute_F_error,absolute_reference_F',comments='')
    for no,H in enumerate([np.eye(3,dtype=int),np.diag([2,1,1]),np.array([[2,1,0],[0,1,0],[0,0,1]])]):
        model=expand(source,H); det=round(np.linalg.det(H)); h=hp@H.T
        local=factors_for(model,h)
        actual=structure_factors(model,h,local,adp_mode='none')
        audit.amplitude(f'VT07_H{no}_embedded_parity',actual,det*library,model,h,local,H)
        # Complete declared supercell grid includes extra satellites.
        hs=grid(6); fs=factors_for(model,hs); actual_all=structure_factors(model,hs,fs,adp_mode='none')
        inv=inverse_fraction(H); expected=[]
        for hv in hs:
            parent=[sum(Fraction(int(hv[j]))*inv[i][j] for j in range(3)) for i in range(3)]
            expected.append(det*engine.calculate_sf_from_small_structure(original,[int(x) for x in parent]) if all(x.denominator==1 for x in parent) else 0j)
        audit.amplitude(f'VT07_H{no}_complete_grid_parity',actual_all,np.array(expected),model,hs,fs,H)
        cif_roundtrip(model,out,audit,f'VT07_H{no}_cif_roundtrip')
    return {'source_sites':len(sites),'asymmetric_sites':len(original.sites),
            'weighted_composition_per_cell':source.composition,
            'normalization_to_Ti2O7':{k:v/4 for k,v in source.composition.items()},
            'normalization_note':'Ti2O7 reference division by four; not a CIF-provided Z',
            'miller_vectors':len(hp),'adp_policy':'explicit zero-ADP derivative; source ADPs unknown',
            'factor_policy':'neutral IT92, no anomalous factors; table shared with Gemmi reference',
            'scope':'geometry and structure-factor transfer only',
            'native_profile_parity':'NOT_ASSESSED','observed_structure_inference':'NOT_ASSESSED'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--stage',choices=['synthetic','external','all'],default='all');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    start=time.time(); frozen=freeze(); audit=Audit()
    (a.output/'FREEZE.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'hashes':frozen,'runner_sha256':sha(Path(__file__))},indent=2)+'\n')
    result={'status':'RUNNING','stage':a.stage,'environment':{'python':platform.python_version(),'numpy':np.__version__,'gemmi':gemmi.__version__},'protocol':'v1','checks':audit.checks}
    try:
        if a.stage in ['synthetic','all']:result['synthetic']=run_synthetic(a.output,audit)
        if a.stage in ['external','all']:result['external']=run_external(a.output,audit)
        audit.check('frozen_core_and_protocol_unchanged',freeze()==frozen)
        result['status']='PASS_BOUNDED_CONTROLS' if all(x['status'] in ['PASS','NOT_APPLICABLE'] for x in audit.checks) else 'FAIL_RETAINED'
    except Exception as e:
        import traceback
        result.update(status='ERROR_RETAINED',error=str(e),traceback=traceback.format_exc())
    result['elapsed_seconds']=time.time()-start
    (a.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'checks':len(audit.checks),'failed':[x['name'] for x in audit.checks if x['status']=='FAIL'],'elapsed_seconds':result['elapsed_seconds'],'error':result.get('error')}))
    return 0 if result['status']=='PASS_BOUNDED_CONTROLS' else 1

if __name__=='__main__':raise SystemExit(main())
