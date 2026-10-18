"""Offline checks for isolated experimental video training (no downloads/model)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

spec = importlib.util.spec_from_file_location('video_candidate', Path(__file__).resolve().parents[1] / 'train_video_candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class VideoCandidateTests(unittest.TestCase):
    def test_recording_group_keeps_youtube_segments_together(self):
        left = {'source_model': 'MSVD', 'file_name': 'videos/real/MSVD/abc_xyz_10_20.mp4'}
        right = {**left, 'file_name': 'videos/real/MSVD/abc_xyz_30_40.mp4'}
        self.assertEqual(candidate.source_group(left), candidate.source_group(right))

    def test_creator_group_keeps_sora_clips_together(self):
        left = {'source_model': 'Sora', 'file_name': 'videos/fake/Sora/creator_123%2Fmd.mp4'}
        right = {**left, 'file_name': 'videos/fake/Sora/creator_456%2Fmd.mp4'}
        self.assertEqual(candidate.source_group(left), candidate.source_group(right))

    def test_temporal_features_are_video_level(self):
        sequence = np.array([[1., 3.], [3., 5.], [5., 7.]])
        result = candidate.aggregate(sequence)
        np.testing.assert_allclose(result[:2], [3, 5])
        np.testing.assert_allclose(result[-2:], [2, 2])
        self.assertEqual(result.shape, (6,))

    def test_identical_frames_have_zero_temporal_change(self):
        result = candidate.aggregate(np.ones((6, 3)))
        np.testing.assert_array_equal(result[3:], np.zeros(6))

    def test_frame_degradation_preserves_count_and_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 6, (256, 256))
            self.assertTrue(writer.isOpened())
            try:
                for i in range(12):
                    writer.write(np.full((256, 256, 3), i * 15, dtype=np.uint8))
            finally:
                writer.release()
            for compressed in (False, True):
                frames = candidate.frames(path, compressed)
                self.assertEqual(len(frames), candidate.FRAME_COUNT)
                self.assertTrue(all(frame.size == (224, 224) for frame in frames))

    def test_short_clip_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'short.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 6, (256, 256))
            writer.write(np.zeros((256, 256, 3), dtype=np.uint8))
            writer.release()
            with self.assertRaises(ValueError):
                candidate.frames(path)

    def test_confusion_matrix_label_order(self):
        result = candidate.metrics(np.array([0, 0, 1, 1]), np.array([.1, .8, .3, .9]))
        self.assertEqual(result['confusion_matrix_real_fake'], [[1, 1], [1, 1]])
        self.assertEqual(result['accuracy'], .5)

    def test_domain_and_label_weights_do_not_overcount_largest_dataset(self):
        rows = [{'source_model': 'MSVD', 'label': 0}] * 10
        rows += [{'source_model': 'Sora', 'label': 1}] * 20
        rows += [{'source_model': 'VidTIMIT', 'label': 0}, {'source_model': 'DeepfakeTIMIT-HQ', 'label': 1}]
        weights = candidate.domain_label_weights(rows)
        masses = {}
        for row, weight in zip(rows, weights):
            key = candidate.domain(row), row['label']
            masses[key] = masses.get(key, 0) + weight
        np.testing.assert_allclose(list(masses.values()), [8, 8, 8, 8])

    def test_blank_video_is_insufficient_evidence_not_fake(self):
        with self.assertRaises(ValueError):
            candidate.require_visual_information([candidate.Image.new('RGB', (224, 224), 'red')] * 6)


if __name__ == '__main__':
    unittest.main()
