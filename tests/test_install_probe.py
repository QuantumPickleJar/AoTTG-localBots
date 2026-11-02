import sys
import tempfile
import unittest
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
    def test_requires_data_dir(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError): inspect(Path(temp))
