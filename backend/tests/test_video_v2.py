"""Offline invariants for the isolated local video candidate."""
import sys
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import train_video_v2 as v


class VideoV2Tests(unittest.TestCase):
    def test_low_quality_swap_is_same_domain(self):
        self.assertEqual(v.domain({'source_model':'DeepfakeTIMIT-LQ'}), 'face-swap')

    def test_each_domain_label_gets_equal_weight(self):
        rows = [{'source_model':'MSVD','label':0}] * 5
        rows += [{'source_model':'Sora','label':1}] * 2
        rows += [{'source_model':'VidTIMIT','label':0}]
        rows += [{'source_model':'DeepfakeTIMIT-LQ','label':1}] * 3
        weights = v.weights(rows)
        masses = {}
        for row, weight in zip(rows, weights):
            key = v.domain(row), row['label']
            masses[key] = masses.get(key,0) + weight
        self.assertTrue(np.allclose(list(masses.values()), len(rows)/4))

    def test_texture_deterministic_finite(self):
        rng = np.random.default_rng(1)
        images = [Image.fromarray(rng.integers(0,256,(224,224,3),dtype=np.uint8)) for _ in range(6)]
        value = v.texture(images)
        self.assertEqual(value.shape,(68,))
        self.assertTrue(np.isfinite(value).all())
        np.testing.assert_array_equal(value, v.texture(images))

    def test_static_temporal_difference_is_zero(self):
        gray = np.random.default_rng(2).integers(0,256,(224,224),dtype=np.uint8)
        value = v.texture([Image.fromarray(gray)] * 6)
        np.testing.assert_array_equal(value[-5:], np.zeros(5))

    def test_missing_video_rejected(self):
        with self.assertRaises(ValueError):
            v.sample(Path('missing-do-not-create-video.mp4'))


if __name__ == '__main__':
    unittest.main()
