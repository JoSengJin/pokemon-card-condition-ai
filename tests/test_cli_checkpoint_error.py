from contextlib import nullcontext, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from card_condition.cli import main


class CheckpointErrorTest(unittest.TestCase):
    def test_real_corrupt_and_empty_region_or_observation_checkpoint_returns_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            request=root/'request.json';request.write_text('{"id":"one"}')
            for payload in (b'invalid-checkpoint',b''):
                bad=root/'bad.pt';bad.write_bytes(payload)
                for observation in (False,True):
                    stdout,stderr=io.StringIO(),io.StringIO()
                    argv=['card-condition','listing-predict',str(bad),str(request),'--device','cpu']
                    if observation:argv.extend(['--observation-checkpoint',str(bad)])
                    # Isolate the observation loader only; torch.load still reads the bad file.
                    region_patch=patch('card_condition.listing_model.RegionAnalyzer') if observation else nullcontext()
                    with self.subTest(payload=payload,observation=observation),region_patch,patch('sys.argv',argv),redirect_stderr(stderr),redirect_stdout(stdout):
                        with self.assertRaises(SystemExit) as raised:main()
                    self.assertEqual(1,raised.exception.code)
                    self.assertEqual('',stdout.getvalue())
                    self.assertEqual(dict(error='Invalid or incomplete checkpoint; use Gemini fallback',requires_gemini=True),json.loads(stderr.getvalue()))
                    self.assertNotIn('Traceback',stderr.getvalue())
                    self.assertEqual(payload,bad.read_bytes())

    def test_unsafe_pickle_remains_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);checkpoint=root/'unsafe.pt'
            torch.save({'object':complex(1,2)},checkpoint)
            request=root/'request.json';request.write_text('{"id":"one"}')
            stderr=io.StringIO()
            with patch('sys.argv',['card-condition','listing-predict',str(checkpoint),str(request),'--device','cpu']),redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:main()
            self.assertEqual(1,raised.exception.code)
            self.assertTrue(json.loads(stderr.getvalue())['requires_gemini'])
