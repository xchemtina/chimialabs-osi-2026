"""Extract only pinned CC BY 4.0 VT07 source members; never infer model parity."""
from pathlib import Path
import argparse, hashlib, json, stat, zipfile

ARCHIVE_SHA256 = '4786813feccc228e623b4646e151d03096c1e95cd9919b03e8140e86eeed8b51'
MEMBERS = {
    'observed.xye': ('Cif_files_and_data/x_0p85/300_K/811900-mac-001_reb_0002.xye', '498fb418f94ed7a31db2ac3f119cf8fd4afc52d15b76ecd34620776f6ac474e5'),
    'source.cif': ('Cif_files_and_data/x_0p85/Cif_files/x_0p85_300K_A2_1am.cif', '093c4d1121c232bc9bdda7340738138b0622c0c6804fa3ad28facde29fe324f4'),
    'published.inp': ('Cif_files_and_data/x_0p85/300_K/CaSrTi2O7_P2_1nm_RT_230119_test_FER_P2_1nm.inp', '56bfba9f0af02bd246e3b9452aa2f6c89814f827578553b1fd20cfab584ad070'),
}

def admit(archive, output):
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError('Archive identity mismatch')
    records = {}
    with zipfile.ZipFile(archive) as z:
        for name, (member, expected) in MEMBERS.items():
            info = z.getinfo(member)
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Expected regular source member')
            if Path(member).is_absolute() or '..' in Path(member).parts:
                raise ValueError('Unsafe member')
            data = z.read(info)
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Source member identity mismatch')
            target = output / name
            if target.is_symlink():
                raise ValueError('Symlink output refused')
            if target.exists():
                if target.read_bytes() != data:
                    raise ValueError('Refusing to replace differing source')
            else:
                with target.open('xb') as f:
                    f.write(data)
            records[name] = {'member': member, 'bytes': len(data), 'sha256': expected}
    receipt = {'archive_sha256': digest, 'members': records,
               'doi': '10.6084/m9.figshare.12446306.v1', 'license': 'CC BY 4.0',
               'status': 'SOURCE_BYTES_VERIFIED_PROFILE_IDENTITY_UNRESOLVED'}
    (output / 'SOURCE_FILES.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args()
    print(json.dumps(admit(a.archive, a.output), indent=2))
