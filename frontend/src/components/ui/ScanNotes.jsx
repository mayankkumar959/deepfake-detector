export default function ScanNotes({ warnings, evaluation, retentionHours = 24, isVideo = false }) {
  return (
    <div className="mt-5 text-xs text-fortexa-muted">
      <p className="text-center">Results can be wrong; they are not proof of authenticity.{isVideo ? ' Video checks use sampled frames only.' : ''}</p>
      <details className="mt-3 rounded-xl border border-white/10 px-4 py-3">
        <summary className="cursor-pointer font-medium hover:text-white">Detection limits & file information</summary>
        <div className="mt-3 space-y-2 leading-relaxed">
          {warnings?.length ? warnings.map(warning => <p key={warning}>{warning}</p>) : <>
            <p>AI-generated vs real photos, including people, objects and scenes. Compression alone does not make a photo AI-generated.</p>
            <p>Videos use sampled frames, not audio or motion detection. Images need at least 224 × 224 pixels.</p>
            <p>Images: JPG, PNG, WebP, BMP. Videos: MP4, MOV, AVI, MKV, WebM. Max 200 MB; videos up to 5 minutes.</p>
            <p>Scans are private to this browser and expire after {retentionHours} hours.</p>
          </>}
          {evaluation && <p>Evaluation: {evaluation.evaluation_scope || evaluation.message}</p>}
          {evaluation?.test_metrics && <p>Small-study test: {(evaluation.test_metrics.accuracy * 100).toFixed(1)}% on {evaluation.test_metrics.samples} images. Not measured accuracy across all generators or videos.</p>}
        </div>
      </details>
    </div>
  )
}
