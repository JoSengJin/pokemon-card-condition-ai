"""Publish a finished evaluation report whole, never replacing an existing or competing file."""
import json
import os
from pathlib import Path
import tempfile


def write_new_report(output, report):
    output = Path(output)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                     prefix=f'.{output.name}.', suffix='.tmp') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
        # A hard link fails if the name appeared meanwhile, so a competing report is kept.
        os.link(stream.name, output)
