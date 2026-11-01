import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import pack_assets as pack
import triage_game as triage
import raw_to_png as screenshot

class ToolTests(unittest.TestCase):
    def test_palette_preserves_single_color_and_partial_alpha(self):
        im=Image.new('RGBA',(2,1));im.putdata([(255,0,0,128),(0,0,255,0)])
        indices,palette=pack.quantize_indexed8(im)
        self.assertEqual(b''.join(palette[i*4:i*4+4] for i in indices),im.tobytes())

    def test_high_color_images_fall_back_without_losing_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            d=Path(temporary);(d/'assets').mkdir()
            im=Image.new('RGBA',(257,1));im.putdata([(i%256,i//256,42,128) for i in range(257)])
            im.save(d/'assets/gradient.png');pack.pack_assets(d/'assets',d/'game.pack')
            b=(d/'game.pack').read_bytes();_,version,count,start=struct.unpack_from('<4sIII',b)
            entry=struct.unpack_from('<128sHHHHII',b,16)
            self.assertEqual(entry[1],pack.TYPE_SPRITE_RGBA32)
            self.assertEqual(b[start:],im.tobytes())

    def test_raw_container_cannot_be_reported_as_successful_pack(self):
        with tempfile.TemporaryDirectory() as temporary:
            d=Path(temporary);(d/'data.win').write_bytes(b'opaque'); (d/'README.txt').write_text('PC game')
            with self.assertRaises(ValueError):
                pack.pack_assets(d,d/'game.pack')
            self.assertFalse((d/'game.pack').exists())

    def test_opaque_inventory_reports_unknown(self):
        result=triage.analyze_feasibility(123456,{'.assets':123456},{'engine':'Unity'})
        self.assertTrue(result['feasibility'].startswith('UNKNOWN'))

    def test_screenshot_uses_active_page_and_stride(self):
        with tempfile.TemporaryDirectory() as temporary:
            d=Path(temporary);(d/'fb').write_bytes(bytes(12)+bytes([0,0,255,255,255,0,0,255])+bytes(4))
            screenshot.convert_fb_to_png(d/'fb',d/'shot.png',width=2,height=1,y_offset=1,stride=12,rotate_180=False)
            with Image.open(d/'shot.png') as im:self.assertEqual([im.getpixel((i,0)) for i in range(2)],[(255,0,0,255),(0,0,255,255)])

    def test_native_layout_rejection_color_stride_pan_and_bounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            exe=Path(temporary)/'core-test'
            subprocess.run(['gcc','-std=c11','-Wall','-Wextra',str(ROOT/'tests/core_framebuffer.c'),'-o',str(exe),'-lpthread'],check=True,capture_output=True)
            subprocess.run([str(exe)],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
