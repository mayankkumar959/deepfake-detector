import sys
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import train_image_v2 as training
from prepare_image_v2 import consolidate


class ImageV2Tests(unittest.TestCase):
    def test_class_and_source_weighting(self):
        rows = [{'label':0,'source':'camera-a'}]*4+[{'label':0,'source':'camera-b'}]
        rows += [{'label':1,'source':'dalle3'}]*2+[{'label':1,'source':'sdxl'}]*3
        weights = training.weights(rows)
        mass = {}
        for row,weight in zip(rows,weights):
            key = row['label'],row['source']
            mass[key] = mass.get(key,0)+weight
        np.testing.assert_allclose(list(mass.values()),len(rows)/4)

    def test_compression_preserves_input_and_generates_all_views(self):
        rng = np.random.default_rng(1)
        pixels = rng.integers(0,256,(800,1000,3),dtype=np.uint8)
        image = Image.fromarray(pixels)
        generated = [training.view(image,name) for name in training.VIEWS]
        np.testing.assert_array_equal(np.asarray(image),pixels)
        self.assertEqual(generated[0].size,(1000,800))
        self.assertEqual(max(generated[-1].size),512)
        self.assertEqual(len(generated),4)
        self.assertTrue(all(i.mode=='RGB' for i in generated))

    def test_unknown_view_rejected(self):
        with self.assertRaises(ValueError):
            training.view(Image.new('RGB',(224,224)),'unknown')

    def test_conflicting_identical_pixels_rejected(self):
        rows = [{'label':label,'group':str(label),'pixel_sha256':'same','sha256':str(label),'phash64':'0'} for label in (0,1)]
        with self.assertRaises(ValueError):
            consolidate(rows)

    def test_near_duplicate_of_observed_test_stays_diagnostic(self):
        rows = [{'label':0,'group':'old','pixel_sha256':'a','sha256':'a','phash64':'0000000000000000','split':'diagnostic'},
                {'label':1,'group':'RAISE-scene:new','pixel_sha256':'b','sha256':'b','phash64':'0000000000000001'}]
        result = consolidate(rows)
        self.assertTrue(all(r['split']=='diagnostic' for r in result))
        self.assertEqual(len({r['group'] for r in result}),1)

    def test_matched_real_and_generator_variants_share_fold(self):
        rows = [{'label':label,'source':str(i),'group':'RAISE-scene:1','pixel_sha256':str(i),
                 'sha256':str(i),'phash64':f'{i:016x}'} for i,label in enumerate([0,1,1,1])]
        result = consolidate(rows)
        self.assertEqual(len({r['split'] for r in result}),1)

    def test_folding_scaler_matches_binary_logit(self):
        rng = np.random.default_rng(3)
        x = rng.normal(size=(20,4)); labels = np.arange(20)%2
        head = training.make_pipeline(training.StandardScaler(),training.LogisticRegression()).fit(x,labels)
        scaler,linear = head.steps[0][1],head.steps[1][1]
        weight = linear.coef_[0]/scaler.scale_
        bias = linear.intercept_[0]-weight@scaler.mean_
        np.testing.assert_allclose(training.sigmoid(x@weight+bias),head.predict_proba(x)[:,1],rtol=1e-6)


if __name__=='__main__':
    unittest.main()
