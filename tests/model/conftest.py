# Copyright (c) 2026 Christoph Souris

import json
import os


def load_sample_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        return json.load(f)
