from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]

class IPadMetadataTests(unittest.TestCase):
    def setUp(self):
        script = ROOT / 'tools/validate_ipad_bundle.py'
        self.assertTrue(script.exists(), 'built iPad bundle validator missing')
        spec = importlib.util.spec_from_file_location('ipad_bundle', script)
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def complete(self):
        return {'UISupportedInterfaceOrientations~ipad': ['UIInterfaceOrientationPortrait',
            'UIInterfaceOrientationPortraitUpsideDown', 'UIInterfaceOrientationLandscapeLeft',
            'UIInterfaceOrientationLandscapeRight'], 'UILaunchScreen': {}, 'UIRequiresFullScreen': False}

    def test_requires_all_ipad_orientations_and_launch_configuration(self):
        self.assertEqual(self.module.validate(self.complete()), [])
        info = self.complete(); info['UISupportedInterfaceOrientations~ipad'].pop()
        self.assertIn('all_ipad_orientations_required', self.module.validate(info))
        info = self.complete(); del info['UILaunchScreen']
        self.assertIn('launch_configuration_required', self.module.validate(info))
        info = self.complete(); info['UIRequiresFullScreen'] = True
        self.assertIn('fullscreen_opt_out_not_allowed', self.module.validate(info))

    def test_generic_orientations_and_storyboard_are_valid_alternatives(self):
        info = self.complete()
        info['UISupportedInterfaceOrientations'] = info.pop('UISupportedInterfaceOrientations~ipad')
        info['UILaunchStoryboardName'] = 'LaunchScreen'; del info['UILaunchScreen']
        self.assertEqual(self.module.validate(info), [])

if __name__ == '__main__': unittest.main()
