"""Pinned H4 preparation bootstrap; no installation, MT5 connection or orders."""
import io,zipfile,hashlib,urllib.request,sys,os,subprocess
from pathlib import Path
from uuid import uuid4
REVISION='145bec6190b1a6533f3e4be6eaff227df990cdf4'
PINS={'lsr02_mt5_bridge.py': 'd7a798e286d36418f702bd78f434dc62c5f930bbdb524270da047cd0403aaf16', 'lsr02_regime.py': '8b4a504caeea2fd7f7654b2cbe673b9c4a4c5ebd35fbb69d873a89d1c6c8bab9', 'lsr02_replay.py': 'bd7d3e43428126794923bebe1e4e51a012b49340abf8788c4f2ead826f817383', 'lsr02_sequence.py': '043f037cffdf1b30cb89be3a95176672900447fbccce4891c4f0d1d722a2f1da', 'lsr02_structure.py': '873fe9d8951d80dc2e79082f5bee9c3ba162a3b0c77ba7c212a4cc94d0c04a1b', 'lsr03_adapter.py': '6470b4122d1731446d9836929a7c8dfd95abf94ef2ff454a482f2ee4f7bc70ff', 'lsr03_mt5_pilot.py': '5114058e0fb3aeb480f6101bc792f642b4ef54fc8eb618042be76149ec6599a8', 'lsr03_tick_study.py': '9a6ae6ee7124d466016063767c9eeadce459d42a51503233453b243f00b8c9b6', 'lsr03_vhf.py': '20d7b8486434af192078cdeba8349900a407c9e9197183a0c4c8b1698c90b0ba', 'lsr04_account_gate.py': 'b5e15e6f3346353d977c3aec8602b5d418da588fc9c120ae3808d0e10e0a5c13', 'lsr04_daily_reconciliation.py': '8e08f8aa9f956fc784fbe88cc674094c673b0cbc6ed1da65c18a30848f6264bd', 'lsr04_deal_groups.py': 'bd58424a99a70ef5cbf49ab60746630db819cc969f9aef24adf578855598dfc4', 'lsr04_mt5_account_sync.py': '9ab7934a5d62321fd6657c8b516ce22d2b5971b5abdcd755f2601f1c0021780c', 'lsr04_mt5_adaptive.py': '536ecc420a5c84467f944940b1d0ff115297e4a9d0ef268f3a7ce833dcaa07b9', 'lsr04_mt5_position_risk.py': '9db0c4915853195cd3584a15f517d963107dd21199577230a75c930566bf51c5', 'lsr04_mt5_ticks.py': '2dc13298cf4f95c65a066de18ed144922959976952b3274c2d3c629ea295d477', 'lsr04_tick_archive.py': 'e77594d24005c71da743364a7e638ab7d52617afcefd5b93c54e576e53d61da7', 'lsr04_tick_catalog.py': 'd2385d494f7e4d3d50a1b07c519cd0795fbb4158f0b290296777fe0a87d8da87', 'lsr04_tick_fills.py': 'ff30b59e09e52d521103d6debd31d75419544489759308955ddb261a4281b3fc', 'lsr04_tick_quality.py': '354fa24c975c96ecc00a2f0ffe2f6f38b0df86975ff147044593bb8145b279f3', 'orrery_h4_batch_chain.py': '9125626179f5ac87c2c33a9596f3c52d086dc42a6f1630374327c25e77b99769', 'orrery_h4_batch_verify.py': '1184ea66a5c4d6c3e32ad29216a69e0db824c4e8dae7683650e2d2b03c30411b', 'orrery_h4_pc_workflow.py': 'db154db64236e71b92fffd09ce465c10363842f296e62ad8fce7426b5e71a062', 'orrery_h4_reconciliation_batch.py': '26cbd4d4d3c93cb47e622d3f7acf7c311b987d9254da409b5b79cc88bda5195a', 'orrery_h4_reconciliation_plan.py': '4cd2354bc1b19ccd3d31753ca606e68249ce1ad8c6dd0b0b0dc99974a79ae87a', 'orrery_mt5_history_check.py': 'ba45ddf6062c34aca5219668d81ae9f38f49a747e1bfe1ef706afc67f36f10aa'}
MAX_ZIP=20*1024*1024
MAX_FILE=2*1024*1024


def download():
    url='https://github.com/kosei131/orrery-mobile/archive/'+REVISION+'.zip'
    with urllib.request.urlopen(url,timeout=60) as response:
        allowed=(url,'https://codeload.github.com/kosei131/orrery-mobile/zip/'+REVISION)
        if response.geturl() not in allowed:raise ValueError('Unexpected source redirect')
        raw=response.read(MAX_ZIP+1)
    if len(raw)>MAX_ZIP:raise ValueError('Archive budget exceeded')
    return raw


def prepare(parent, *, archive):
    if not isinstance(archive,bytes) or len(archive)>MAX_ZIP:raise ValueError('Bounded ZIP required')
    selected={};prefix='orrery-mobile-'+REVISION+'/'
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names=z.namelist()
        for name,pin in PINS.items():
            path=prefix+name
            if names.count(path)!=1:raise ValueError('Missing or duplicate pinned source')
            info=z.getinfo(path)
            if info.file_size>MAX_FILE:raise ValueError('Source budget exceeded')
            raw=z.read(path)
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Source pin mismatch')
            compile(raw,name,'exec');selected[name]=raw
    root=Path(parent)/str(uuid4());root.mkdir(parents=True,exist_ok=False)
    for name,raw in selected.items():
        with (root/name).open('xb') as f:f.write(raw)
    (root/'SOURCE_REVISION.txt').write_text(REVISION+'\n',encoding='ascii')
    return root


def main():
    try:
        if sys.platform!='win32' or sys.version_info[:2]!=(3,12):raise ValueError('Windows Python3.12 required')
        root=prepare(Path(os.environ['LOCALAPPDATA'])/'ORRERYFX'/'h4-preparation',archive=download())
        print('PINNED_SOURCE_VERIFIED:',REVISION,flush=True)
        print('LOCAL_OUTPUT:',root,flush=True)
        # No --execute: the worker only prepares and verifies the offline plan.
        return subprocess.run([sys.executable,str(root/'orrery_h4_pc_workflow.py'),
            '--output',str(root/'preflight')],cwd=root,timeout=30,check=False).returncode
    except Exception:
        print('BLOCKED: source download, verification or preparation failed. No MT5 execution requested.')
        return 1

if __name__=='__main__':raise SystemExit(main())
