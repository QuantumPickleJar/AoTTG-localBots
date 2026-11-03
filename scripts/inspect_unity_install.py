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
import re
import struct


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
    exe = next((p for p in rootfiles if p.name.lower() == 'aottg2.exe'), None)
    global_managers = data / 'globalgamemanagers'
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
    candidates += [p for p in (assembly, il2cpp, global_managers) if p.is_file()]
    architecture = _pe_architecture(exe) if exe else {'value': 'unavailable', 'machine': None}
    version_hint = _unity_version_hint(global_managers)
    loader_markers = {
        'BepInEx': (folder / 'BepInEx').is_dir(),
        'MelonLoader': (folder / 'MelonLoader').is_dir(),
    }
    return {'layout_hint': guess, 'indicators': indicators,
            'runtime_hints': {'executable_architecture': architecture,
                              'unity_version': version_hint,
                              'loader_directories_present': loader_markers},
            'data_folder': data.name, 'files': [fileentry(p) for p in candidates],
            'cautions': ['File-layout hints do not verify current Unity version or supported injection method.',
                         'PE architecture and globalgamemanagers version strings are local file hints only.',
                         'Does not load or alter game binaries or connect to servers.',
                         'Do not publish proprietary binaries or sensitive user installation paths.']}


def _pe_architecture(exe: Path):
    """Read only the DOS/PE headers; return an architecture hint, not ABI proof."""
    try:
        with exe.open('rb') as stream:
            header = stream.read(64)
            if len(header) < 64 or header[:2] != b'MZ':
                return {'value': 'unknown', 'machine': None}
            pe_offset = struct.unpack_from('<I', header, 0x3C)[0]
            if pe_offset > 16 * 1024 * 1024:
                return {'value': 'unknown', 'machine': None}
            stream.seek(pe_offset)
            pe_header = stream.read(6)
        if len(pe_header) != 6 or pe_header[:4] != b'PE\0\0':
            return {'value': 'unknown', 'machine': None}
        machine = struct.unpack_from('<H', pe_header, 4)[0]
        labels = {0x014C: 'x86', 0x8664: 'x64', 0xAA64: 'arm64'}
        return {'value': labels.get(machine, 'unknown'), 'machine': f'0x{machine:04x}'}
    except OSError:
        return {'value': 'unavailable', 'machine': None}


def _unity_version_hint(path: Path):
    """Search only a small header prefix for a printable Unity version string."""
    if not path.is_file():
        return {'value': None, 'source': 'globalgamemanagers', 'confidence': 'unavailable'}
    try:
        with path.open('rb') as stream:
            prefix = stream.read(4096)
    except OSError:
        return {'value': None, 'source': 'globalgamemanagers', 'confidence': 'unreadable'}
    match = re.search(rb'(?<![0-9])((?:20[0-9]{2}|[5-9][0-9]?)\.[0-9]+\.[0-9]+[abfp][0-9]+)(?![A-Za-z0-9])', prefix)
    return {'value': match.group(1).decode('ascii') if match else None,
            'source': 'first_4096_bytes_of_globalgamemanagers',
            'confidence': 'candidate_string' if match else 'not_found_in_prefix'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('install_dir')
    p.add_argument('--out', default='build_preflight.json')
    args=p.parse_args()
    result=inspect(Path(args.install_dir))
    Path(args.out).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__=='__main__':main()
