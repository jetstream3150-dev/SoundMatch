import math
import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from online_audio import discover_audio, rank_candidates

class FakeResponse:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return self.data

class Tests(unittest.TestCase):
    def test_discovery_filters_license_and_extension(self):
        import json
        data = {'query': {'pages': [
            {'title': 'File:Beat.ogg', 'imageinfo': [{'url': 'https://upload.wikimedia.org/a.ogg','size':123,
              'extmetadata': {'LicenseShortName': {'value': 'CC BY-SA 4.0'}}}]},
            {'title': 'File:NoLicence.wav', 'imageinfo': [{'url': 'https://upload.wikimedia.org/b.wav','size':123}]},
            {'title': 'File:Video.jpg', 'imageinfo': [{'url': 'https://upload.wikimedia.org/a.jpg','size':123,
              'extmetadata': {'LicenseShortName': {'value': 'CC0'}}}]}
        ]}}
        found = discover_audio('beatbox',opener=lambda request,timeout: FakeResponse(json.dumps(data).encode()))
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['license'],'CC BY-SA 4.0')

    def test_rank_audio_uses_actual_waveform(self):
        sr=16000
        duration=9
        x=np.arange(sr*duration)/sr
        y=.2*np.sin(2*np.pi*140*x)*(1+.4*np.sin(2*np.pi*4*x))
        z=.2*np.sin(2*np.pi*2000*x)
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            ref=d/'reference.wav';sf.write(ref,y,sr)
            files={'same':y,'different':z}
            items=[{'url':'https://example.org/'+key+'.wav','title':key,'page':'https://example.org','license':'CC0'} for key in files]
            def download(item,path):
                key=Path(item['url']).stem
                sf.write(path,files[key],sr)
            found=rank_candidates(str(ref),0,8,'beatbox',discovery=lambda *_:items,downloader=download)
            self.assertEqual(len(found),2)
            self.assertEqual(found[0][1]['title'],'same')
            self.assertGreater(found[0][0],found[1][0])

if __name__=='__main__': unittest.main()
