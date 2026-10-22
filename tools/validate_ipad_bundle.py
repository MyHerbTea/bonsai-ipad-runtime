"""Validate built iPad multitasking prerequisites, not runtime UI correctness."""
from pathlib import Path
import argparse
import plistlib

ORIENTATIONS = {'UIInterfaceOrientationPortrait', 'UIInterfaceOrientationPortraitUpsideDown',
                'UIInterfaceOrientationLandscapeLeft', 'UIInterfaceOrientationLandscapeRight'}

def validate(info):
    errors = []
    orientations = info.get('UISupportedInterfaceOrientations~ipad', info.get('UISupportedInterfaceOrientations'))
    if not isinstance(orientations, list) or not ORIENTATIONS.issubset(orientations):
        errors.append('all_ipad_orientations_required')
    if not isinstance(info.get('UILaunchScreen'), dict) and not info.get('UILaunchStoryboardName'):
        errors.append('launch_configuration_required')
    if info.get('UIRequiresFullScreen', False): errors.append('fullscreen_opt_out_not_allowed')
    return errors

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('plist', type=Path); args = p.parse_args()
    errors = validate(plistlib.loads(args.plist.read_bytes()))
    if errors: raise SystemExit(', '.join(errors))
    print('iPad orientations and launch configuration: PASS; runtime multiwindow validation: NOT_RUN')
