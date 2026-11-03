import sys
import tempfile
import unittest
import struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from inspect_unity_install import inspect
class ProbeTests(unittest.TestCase):
    def test_mono_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            (d/'AoTTG2.exe').write_bytes(b'MZexample')
            (d/'AoTTG2_Data'/'Managed').mkdir(parents=True)
            (d/'AoTTG2_Data'/'Managed'/'Assembly-CSharp.dll').write_bytes(b'fake-assembly')
            r=inspect(d)
            self.assertEqual(r['layout_hint'],'mono_indicated')
            self.assertEqual(len(r['files']),2)
    def test_il2cpp_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            (d/'GameAssembly.dll').write_bytes(b'dummy')
            (d/'aottg_Data'/'il2cpp_data'/'Metadata').mkdir(parents=True)
            (d/'aottg_Data'/'il2cpp_data'/'Metadata'/'global-metadata.dat').write_bytes(b'metadata')
            self.assertEqual(inspect(d)['layout_hint'],'il2cpp_indicated')
    def test_architecture_and_unity_version_are_explicit_low_confidence_hints(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            exe=bytearray(0x100)
            exe[:2]=b'MZ'
            struct.pack_into('<I', exe, 0x3C, 0x80)
            exe[0x80:0x84]=b'PE\0\0'
            struct.pack_into('<H', exe, 0x84, 0x8664)
            (d/'AoTTG2.exe').write_bytes(exe)
            (d/'AoTTG2_Data').mkdir()
            (d/'AoTTG2_Data'/'globalgamemanagers').write_bytes(b'UnityPlayer\0 2022.3.44f1\0')
            hints=inspect(d)['runtime_hints']
            self.assertEqual(hints['executable_architecture']['value'],'x64')
            self.assertEqual(hints['executable_architecture']['machine'],'0x8664')
            self.assertEqual(hints['unity_version']['value'],'2022.3.44f1')
            self.assertEqual(hints['unity_version']['confidence'],'candidate_string')
    def test_requires_data_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError): inspect(Path(temp))
