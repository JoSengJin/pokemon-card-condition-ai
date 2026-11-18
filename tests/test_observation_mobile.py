import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from observation_loop_fixture import fixture
from test_observation_collection_contract import contract_fixture
from card_condition.observation_collection_contract import contract_digest
from card_condition.observation_page import render_page


class MobileTests(unittest.TestCase):
    def test_candidate_viewport_export_and_latch_in_node_stub(self):
        packet,assets=fixture();c=contract_fixture()
        with tempfile.TemporaryDirectory() as folder:
            page=Path(folder)/"page.html";page.write_text(render_page(packet,assets,collection_contract=c))
            r=subprocess.run(["node","tests/observation_viewport.test.cjs",str(page)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_wrong_contract_packet_or_profile_is_rejected(self):
        packet,assets=fixture()
        for field in ("packet_id","display_profile"):
            with self.subTest(field=field):
                c=contract_fixture()
                if field=="packet_id":c[field]="0"*64
                else:c[field]["viewport_css"]=[320,600]
                c["contract_id"]=contract_digest(c)
                with self.assertRaises(ValueError):render_page(packet,assets,collection_contract=c)

    def test_default_page_remains_v1_and_null_contract_not_mutated(self):
        packet,assets=fixture();c=contract_fixture();before=copy.deepcopy(c)
        self.assertNotIn('id="collection-out"',render_page(packet,assets))
        self.assertIn('id="collection-out"',render_page(packet,assets,collection_contract=c))
        self.assertEqual(c,before)
