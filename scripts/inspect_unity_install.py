#!/usr/bin/env python3
"""Read-only Unity player layout probe. No injection, decompilation or changes.

Usage: py -3 scripts/inspect_unity_install.py "D:\\Games\\AoTTG2" --out build_preflight.json
This is a structural detector; it cannot determine Unity version or whether a
mod loader will work. Run against the *current* launcher install, not an older one.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def inspect(folder: Path):
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    # Only top-level Unity player dirs. Avoid traversing entire game asset bundle tree.
    rootfiles = sorted(p for p in folder.iterdir() if p.is_file())
    datas = sorted(p for p in folder.iterdir() if p.is_dir() and p.name.lower().endswith('_data'))
    if not datas:
        raise FileNotFoundError('No *_Data directory; select the folder containing AoTTG2.exe')
    data = datas[0]
    managed = data / 'Managed'
    il2cpp = data / 'il2cpp_data' / 'Metadata' / 'global-metadata.dat'
    gameasm = next((p for p in rootfiles if p.name.lower() == 'gameassembly.dll'), None)
    unityplayer = next((p for p in rootfiles if p.name.lower() == 'unityplayer.dll'), None)
    assembly = managed / 'Assembly-CSharp.dll'
    mono = managed / 'mscorlib.dll'
    indicators = {'mono_managed_assembly': assembly.is_file(),
                  'mono_mscorlib': mono.is_file(),
                  'il2cpp_game_assembly': bool(gameasm),
                  'il2cpp_metadata': il2cpp.is_file(),
                  'unity_player': bool(unityplayer)}
    if indicators['il2cpp_game_assembly'] and indicators['il2cpp_metadata']:
        guess = 'il2cpp_indicated'
    elif indicators['mono_managed_assembly']:
        guess = 'mono_indicated'
    else:
        guess = 'unknown_or_mixed'
    def fileentry(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        return {'name': p.name, 'size': p.stat().st_size, 'sha256': h.hexdigest()}
    candidates = [p for p in rootfiles if p.suffix.lower() in ('.exe', '.dll')]
    candidates += [p for p in (assembly, il2cpp, data / 'globalgamemanagers') if p.is_file()]
    return {'layout_hint': guess, 'indicators': indicators,
            'data_folder': data.name, 'files': [fileentry(p) for p in candidates],
            'cautions': ['File-layout hints do not verify current Unity version or supported injection method.',
                         'Does not load or alter game binaries or connect to servers.',
                         'Do not publish proprietary binaries or sensitive user installation paths.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('install_dir')
    p.add_argument('--out', default='build_preflight.json')
    args=p.parse_args()
    result=inspect(Path(args.install_dir))
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__=='__main__':main()
