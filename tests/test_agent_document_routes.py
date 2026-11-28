import hashlib
import re
import unittest
from pathlib import Path

from card_condition.cross_review_auto_sources import review_rules

ROOT = Path(__file__).resolve().parents[1]
# Migration baseline: change these only after reviewing a deliberate policy/approval change.
BASELINE_RULE_HASHES = ['a4b5d189a1a6e88ecc540a8af452af03a98b7285d702d95b876fcce74afe972b', 'c299546cf3654a59d6ad5fd7f77b5741fd26457e0f4b5afad34b6e7169e1fb77', '1a827c5800036ac3b86d4cd06866a988657e42725dfdfde34dd840952bcdb4e6', 'cec3b3773fc7bc036941629e32871aba327ed06674c617ed8a63d06d5f32d527', '52e90b4efd0335a60f8426f7bb35455e2002610fc484dd0416d42eb46c01cc94', 'dfb3588b8fc61ba336531da3bc80dc5e3ee9328bf58b7b7de220e785df9ff10c', 'e6d92985e8bc5e033a8f5b700994b62a18fab96faef784369817346c4808fe40', '1e24bdb3e9f59aea9316322c5d130dc93da66c89c661ef9915d0084040f4f30d', 'b7ef586107c0df09533b5b0f85bb6b9a58d5114d0713ea732c4abf4290adc6ca', 'fe6f5f932615d87f56727834693e084011a7d0d118617a34adb074d54d2eb884', '122a323634a63774d5c0a562825427fa9788192082e5bbe36a2b46dcaf7bf516', '18c9bea9dde6f70dd48d2b98fa2cbaa922c96ef64ca25a9f879cc4de72e669fa', 'fcb4b5a79ade3d6252935c0206b90007e518e38b4c8a74f650d55c9f6341aa8c', 'd71fcf82d2d3ff7065fb38c71e5c2eb16fbe7b854bdcebff9f5bcc50dc3e352c', '2043c9e63aa3ba47794314b29ad163fd15469e339d76f46aea70246a692abe18', 'b8e0fc7db48ea9d6a5c5faab622bb581ff95bb43fa4d7015e3691a3b7fb70005', '4435b790413b247afc996670b1b2bb3a4f59ac82405b7707206da72bf271d207', '09311e305a3b3bf65c7664b981f994040bcee9b23521d03e9834485ea1434ebb', 'fe3810aa2667deef8b7dd1e473cab4adfe84569572cff15ebd9885f06b0a975b', '16a1eb70f097fba47d6e527d5716286b442c2a3d64821a74397a42a24fcb5021', '48e12f458cec2333068fc5ad61d2d22acdebc32ffdc1506b1f9d2c2430e07427', 'dfe74d484c0e1b13f38d503bb4b780b9dd11d61457e3b6b2c31669a4d1b7644a', 'ce1a1485f92a3c7f657d6442880b7f4f7869431677842f35a88a84794ac002f8', '3ce519d86c619852d2cb1e8141f6b4295aecec5d24bb69f9fdf88746af69078a', '8e26cbc7bcc00f7ce2f18bd9852c36dd870708c4970d129a942e40d134112fb8', '68c6387dd567b64cb4d3b9fa67aec17a3d61385ad5f5c198808485410bf00635', '66a0f4cb35e59d517bc9417d79b5b432b22b50074a0e782c8022656566d494d0', '8999b2faedda458904e19950e883342c34b9d9353c9182690efb674411c3860f', '9b37e404227c16237df9886109fdb0f2a52887fbf11de8c127eaa7ceab5ae01e', '0bbe0fd89a9d572cbf10c3e52c51f32b88908ac022cc60dad0d2995f93396554', 'f802db55e271ad203a98c59e4ed97fbceb011e0742edca63780609dbf67591bc', '6832ba780611c96ca76d4af81cdd4925b61bc7fb08d1643e207540e33dba9fc8', '39069bc92c7efd47b581ce40a52f73d00179a90e73507dcf4cee98b63d86fa29', '3844a427da5cc01dfe21396355b75a3817e3fcd1cfd67ac56adaad1c21fdc49c', '8b7cb306221784ee66509e5d5234bf9e2ff17f76d5afb2adcd8d7cb3705000fb', '29fde3dc3b40dadb374d8413b0540b79ee186c8bf333d1720deb89c4665df4af', '781ebef36fb6d96bcdd4a021e531dd3d7a27fd46571136aa635152538299f3d8', 'af1c1b50560e4417b16ce20f719e49be3562830fa27559c5515b8109f81856f0', 'c18867d507724d5b138877a886e29ea1a8015b2c5ad18223c4c0bad8805ae475', 'b7b0255bf5bd420dd5954ec46a2acef9c6d788abf37410ef6ab38c04efc201d9', '60c88a7f085a489592dd9791a872c22c80dfd505d618ad6582d681ec7e803a92', '0b37843264f6b497b57021590687f3e4c8c09d1d721417cf59b3727dabeee48f', 'b645fcadd067ab105fc98b6e7d01f85a3444b20a337966b5a78d8ae57e6dbbde', '8163087aa2ba333822427923784b952f335a69489f968b360b790a556fd32bd0', '44af002b1aa9109747b8b5b83b1e670b4846603db29a49a499bae0be8f69bcb3', '85547d1b0b01c1a1e58fed504ee8d0c90ef5f49a7d866cf41bab31d5b186b0d6']


class AgentDocumentRoutesTest(unittest.TestCase):
    def test_both_agents_enter_the_same_rules_and_task_routes(self):
        self.assertEqual((ROOT/'CLAUDE.md').read_text().strip(), '@AGENTS.md')
        agents = (ROOT/'AGENTS.md').read_text()
        self.assertIn('docs/AGENT_START.md', agents)
        start = (ROOT/'docs/AGENT_START.md').read_text()
        for route in ('PAIR_CODING.md', 'COMMON_EXPERIMENT_RECORDS.md', 'LABELING_PROTOCOL.md',
                      'PROGRESS_CRITERIA.md', 'development-progress.json', 'AUTO_REVIEW_CONTRACT.md'):
            self.assertIn(route, start)
        self.assertIn('권한을 새로 부여하지', start)

    def test_preexisting_instructions_and_approvals_are_preserved(self):
        lines = (ROOT/'AGENTS.md').read_text().splitlines()
        hashes = {hashlib.sha256(l.encode()).hexdigest() for l in lines if l.startswith('- ')}
        self.assertTrue(set(BASELINE_RULE_HASHES).issubset(hashes), 'Existing policy was removed or reworded')

    def test_current_entrypoints_do_not_embed_obsolete_progress(self):
        readme = (ROOT/'README.md').read_text()
        self.assertNotIn('30%', readme)
        self.assertNotIn('67%', readme)
        self.assertIn('development-progress.json', readme)
        self.assertNotIn('usable-card-analysis-v1.0', (ROOT/'AGENTS.md').read_text())
        self.assertIn('로컬 경로 설정', readme)

    def test_hot_documents_and_child_rules_fit_the_existing_budgets(self):
        for name, limit in [('AGENTS.md', 16384), ('README.md', 12288), ('COMMON_EXPERIMENT_RECORDS.md', 28672)]:
            with self.subTest(name=name):
                self.assertLess((ROOT/name).stat().st_size, limit)
        self.assertLess(len(review_rules(ROOT/'AGENTS.md').encode()), 3000)

    def test_navigation_and_relocated_local_links_exist(self):
        names = ['AGENTS.md', 'CLAUDE.md', 'README.md', 'COMMON_EXPERIMENT_RECORDS.md',
                 'docs/AGENT_START.md', 'docs/agent/AUTO_REVIEW_CONTRACT.md',
                 'docs/history/README_BEFORE_AGENT_GUIDE_20261118.md']
        for name in names:
            path = ROOT/name
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                if link.startswith(('https:', 'http:', '#', 'mailto:')):
                    continue
                target = (path.parent/link.split('#')[0]).resolve()
                if target.is_relative_to(ROOT/'artifacts'):
                    continue  # Historical ignored evidence is intentionally absent in implementation worktrees.
                with self.subTest(name=name, link=link):
                    self.assertTrue(target.is_file())
        self.assertIn('agent/AUTO_REVIEW_CONTRACT.md', (ROOT/'COMMON_EXPERIMENT_RECORDS.md').read_text())
