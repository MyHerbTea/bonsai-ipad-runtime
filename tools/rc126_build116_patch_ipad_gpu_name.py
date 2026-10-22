#!/usr/bin/env python3
"""Recognize the exact Apple iPad Metal device-name GPU suffix."""
import argparse
from pathlib import Path
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, replace_once, run_diff_check


def apply(root):
    if run_git(root, 'rev-parse', 'HEAD') != BASE_SHA:
        raise SystemExit('wrong pinned Prism revision')
    path = root / 'ggml/src/ggml-metal/ggml-metal-device.m'
    replace_once(path,
        '    const char * suffix = name + sizeof(prefix) - 1;\n',
        '''    const char * suffix = name + sizeof(prefix) - 1;
    // BONSAI_IPAD_GPU_NAME_116: MTLDevice.name is "Apple M5 GPU" on iPad.
    // Normalize only an exact terminal " GPU", then retain the model table's
    // exact comparison. Unknown models and arbitrary trailing text stay generic.
    char normalized[128];
    const size_t length = strlen(suffix);
    if (length > 4 && length < sizeof(normalized) && strcmp(suffix + length - 4, " GPU") == 0) {
        memcpy(normalized, suffix, length - 4);
        normalized[length - 4] = '\\0';
        suffix = normalized;
    }
''')
    run_diff_check(root)
    print('Build116 iPad exact GPU name normalization: source PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prism_dir', type=Path)
    apply(parser.parse_args().prism_dir.resolve())
