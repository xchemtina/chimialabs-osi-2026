"""Render the public observation series with the local Rust Powder Plot binary."""
from pathlib import Path
import argparse, hashlib, json, subprocess, zipfile
import numpy as np
from admit_vt07 import ARCHIVE_SHA256

MEMBERS = {
300:'Cif_files_and_data/x_0p85/300_K/811900-mac-001_reb_0002.xye',
473:'Cif_files_and_data/x_0p85/473_K/811998-mac-001_reb_0002.xye',
623:'Cif_files_and_data/x_0p85/623_K/812085-mac-001_reb_0002.xye',
773:'Cif_files_and_data/x_0p85/773_K/812171-mac-001_reb_0002.xye',
873:'Cif_files_and_data/x_0p85/873_K/812231-mac-001_reb_0002.xye'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--plotter',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True,help='New directory; will not overwrite an earlier export')
    a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    if hashlib.sha256(a.archive.read_bytes()).hexdigest()!=ARCHIVE_SHA256:raise ValueError('Archive identity mismatch')
    inputs=a.output/'inputs';inputs.mkdir();records=[]
    with zipfile.ZipFile(a.archive) as z:
        for temp,member in MEMBERS.items():
            content=z.read(member); target=inputs/f'{temp}K.xye';target.write_bytes(content)
            values=np.loadtxt(target)
            if values.shape[1]!=3 or not np.isfinite(values).all() or not np.all(np.diff(values[:,0])>0):raise ValueError('Malformed observation')
            records.append({'temperature_label_K':temp,'temperature_source':'deposit folder name only','member':member,'sha256':hashlib.sha256(content).hexdigest(),'rows':len(values),'nonpositive_sigma_two_theta':values[values[:,2]<=0,0].tolist(),'path':str(target)})
    spec={'title':'Layered titanate: high-resolution observations','subtitle':'Diamond I11 | nominal temperatures from deposit folders | no fit or phase assignment',
          'paths':[r['path'] for r in records],'parameters':list(MEMBERS),'parameter_label':'Nominal temperature (K)','x_label':'2θ (°)',
          'output':str(a.output/'vt07-series.svg'),'view':'both','normalization':'none','color_scale':'asinh','colormap':'viridis','max_traces':5,'x_range':[7,40],
          'footnotes':['Fernando Pomiro, Figshare 10.6084/m9.figshare.12446306.v1, CC BY 4.0.','Rows follow selected-file order sorted by folder-labelled temperature; chronology is not independently verified.','Measured intensities unchanged; waterfall adds offsets; contour interpolation is display only.','One sigma=0 point at 0.19 degrees in the 473 K scan lies outside this view; no fitting is performed.']}
    spec_path=a.output/'export.json';spec_path.write_text(json.dumps(spec,indent=2)+'\n')
    subprocess.run([str(a.plotter.resolve()),'--export-figure',str(spec_path)],check=True)
    (a.output/'INPUTS.json').write_text(json.dumps(records,indent=2)+'\n')
    print(a.output/'vt07-series.svg')

if __name__=='__main__':main()
