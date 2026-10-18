export default function ScanNotes({ warnings, evaluation, videoEvaluation, retentionHours = 24, isVideo = false }) {
  const metrics = evaluation?.test_metrics
  const sampleCount = metrics?.samples ?? metrics?.images ?? metrics?.examples
  const videoMetrics = videoEvaluation?.test_metrics?.clean
  const videoCount = videoMetrics?.samples ?? videoMetrics?.images ?? videoMetrics?.examples
  return (
    <div className="mt-5 text-xs text-fortexa-muted">
      <p className="text-center">Results can be wrong; they are not proof of authenticity.{isVideo ? ' Video checks use a trained visual head on sampled frames; audio is not analyzed.' : ''}</p>
      <details className="mt-3 rounded-xl border border-white/10 px-4 py-3">
        <summary className="cursor-pointer font-medium hover:text-white">Detection limits & file information</summary>
        <div className="mt-3 space-y-2 leading-relaxed">
          {warnings?.length ? warnings.map(warning => <p key={warning}>{warning}</p>) : <>
            <p>AI-generated vs real photos, including people, objects and scenes. Compression alone does not make a photo AI-generated.</p>
            <p>Videos use six centred frames for the trained visual head plus a per-frame timeline; audio and lip-sync consistency are not analyzed. Images need at least 224 × 224 pixels.</p>
            <p>Images: JPG, PNG, WebP, BMP. Videos: MP4, MOV, AVI, MKV, WebM. Max 200 MB; videos up to 5 minutes.</p>
            <p>Scans are private to this browser and expire after {retentionHours} hours.</p>
          </>}
          {evaluation && <p>Image evaluation: {evaluation.evaluation_scope || evaluation.message}</p>}
          {metrics?.accuracy != null && <p>Small-study image test: {(metrics.accuracy * 100).toFixed(1)}%{sampleCount ? ` on ${sampleCount} images` : ''}. Not measured accuracy across all generators or videos.</p>}
          {videoMetrics?.accuracy != null && <p>Small-study video test (visual only): {(videoMetrics.accuracy * 100).toFixed(1)}%{videoCount ? ` on ${videoCount} clips` : ''}. Audio and unseen generators are not covered.</p>}
        </div>
      </details>
    </div>
  )
}
