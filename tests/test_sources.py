import importlib.util,io,struct,unittest,zlib
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('sources',Path(__file__).parents[1]/'tools/index_sources.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class Sources(unittest.TestCase):
 def test_range_refuses_full_download(self):
  with patch.object(s,'fetch',return_value=(b'1234',{})):
   with self.assertRaisesRegex(ValueError,'full package refused'):s.RemoteZip('https://example.com/app.ipa',100).read(4)
 def test_budget_prevents_request(self):
  with patch.object(s,'fetch') as fetch:
   with self.assertRaisesRegex(ValueError,'budget'):s.RemoteZip('https://example.com/app.ipa',10_000_000).read(3_000_000)
   fetch.assert_not_called()
 def test_cgbi_unpremultiplies_bgra(self):
  def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+b'0000'
  compressor=zlib.compressobj(wbits=-15);data=compressor.compress(bytes([0,10,20,30,128]))+compressor.flush()
  raw=b'\x89PNG\r\n\x1a\n'+chunk(b'CgBI',b'')+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',data)
  self.assertEqual(s.decode_image(raw).getpixel((0,0)),(59,39,19,128))
if __name__=='__main__':unittest.main()
class DeclaredIcons(unittest.TestCase):
 def test_ios_uses_plist_icon_instead_of_tutorial_or_atlas(self):
  import zipfile,plistlib
  data=io.BytesIO()
  from PIL import Image
  image=io.BytesIO();Image.new('RGBA',(40,40),'blue').save(image,'PNG')
  with zipfile.ZipFile(data,'w') as z:
   z.writestr('Payload/A.app/Info.plist',plistlib.dumps({'CFBundleIconFiles':['Launcher']}))
   z.writestr('Payload/A.app/Launcher.png',image.getvalue())
   z.writestr('Payload/A.app/tutorial_icon@2x.png',b'wrong')
   z.writestr('Payload/A.app/assets/appicon_atlas.png',b'wrong')
  with patch.object(s,'RemoteZip',return_value=io.BytesIO(data.getvalue())):
   raw,meta=s.zip_icon('https://example.com/test.ipa',len(data.getvalue()),ios=True)
  self.assertEqual(raw,image.getvalue())
