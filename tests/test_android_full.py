import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('full',Path(__file__).parents[1]/'tools/index_android_full.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FullIndex(unittest.TestCase):
 def collect(self,pages):
  it=iter(pages);return m.collect(lambda cursor:next(it),lambda *a,**kw:None)
 def test_cursor_and_deduplication(self):
  rows,total=self.collect([{'total':2,'items':[{'identifier':'b','title':'B'}],'cursor':'next'},{'items':[{'identifier':'a'},{'identifier':'b','title':'B'}]}]);self.assertEqual(rows,[['a','a'],['b','B']]);self.assertEqual(total,2)
 def test_repeated_cursor_rejected(self):
  with self.assertRaisesRegex(ValueError,'Repeated cursor'):self.collect([{'items':[{'identifier':'a'}],'cursor':'x'},{'items':[{'identifier':'b'}],'cursor':'x'}])
 def test_incomplete_export_rejected(self):
  with self.assertRaisesRegex(ValueError,'Incomplete export'):self.collect([{'total':100,'items':[{'identifier':'a'}]}])
 def test_empty_export_rejected(self):
  with self.assertRaisesRegex(ValueError,'Empty export'):self.collect([{'total':0,'items':[]}])
if __name__=='__main__':unittest.main()
