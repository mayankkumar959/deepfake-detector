// Builds a printable PDF report for a completed scan.
// jsPDF is imported lazily so the main bundle only pays for it on download.
import { mediaUrl } from '../api/client'

const PAGE = { w: 210, h: 297, margin: 14, footer: 18 }
const CW = PAGE.w - PAGE.margin * 2
const INK = [17, 24, 39]
const MUTED = [108, 122, 117]
const NOTE = [55, 68, 62]
const LINE = [223, 230, 226]
const ACCENT = [16, 185, 129]
const TRACK = [233, 238, 235]

const VERDICTS = {
  fake: { label: 'Likely AI-generated', fg: [185, 28, 28], bg: [254, 226, 226], bar: [220, 38, 38] },
  real: { label: 'Likely real photo', fg: [4, 120, 87], bg: [209, 250, 229], bar: [16, 185, 129] },
  inconclusive: { label: 'Inconclusive', fg: [180, 83, 9], bg: [254, 243, 199], bar: [245, 158, 11] },
}

const fmtDate = (iso) => {
  try {
    return new Date(iso).toLocaleString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return String(iso || '—')
  }
}

const fmtSize = (bytes) => {
  if (bytes == null) return '—'
  return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

const pct = (value) => (typeof value === 'number' && Number.isFinite(value) ? Math.round(value * 100) : null)

// Fetches a scan media file and converts it to a bounded-size JPEG data URL,
// because embedding full-resolution uploads would bloat the PDF.
async function fetchImageData(scan, filename, maxDim = 1500) {
  const response = await fetch(mediaUrl(scan, filename))
  if (!response.ok) throw new Error(`${filename} unavailable`)
  const blob = await response.blob()
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(blob)
    const image = new Image()
    image.onload = () => {
      try {
        const scale = Math.min(1, maxDim / Math.max(image.naturalWidth, image.naturalHeight))
        const width = Math.max(1, Math.round(image.naturalWidth * scale))
        const height = Math.max(1, Math.round(image.naturalHeight * scale))
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)
        ctx.drawImage(image, 0, 0, width, height)
        resolve({ dataUrl: canvas.toDataURL('image/jpeg', 0.86), width, height })
      } catch (error) {
        reject(error)
      } finally {
        URL.revokeObjectURL(objectUrl)
      }
    }
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      reject(new Error(`${filename} decode failed`))
    }
    image.src = objectUrl
  })
}

export async function downloadScanReport(scan) {
  if (!scan?.id) return
  const { jsPDF } = await import('jspdf')
  const report = scan.report || {}
  const isVideo = scan.media_type === 'video'
  const verdict = VERDICTS[scan.verdict] || VERDICTS.inconclusive
  const aiScore = pct(scan.fake_probability)
  const realScore = pct(report.real_probability) ?? (aiScore != null ? 100 - aiScore : null)

  const preview = await (isVideo ? fetchImageData(scan, 'thumbnail.jpg', 1200) : fetchImageData(scan, 'original')).catch(() => null)

  const doc = new jsPDF({ unit: 'mm', format: 'a4', compress: true })
  let y = PAGE.margin

  const text = (str, x, yTop, opts = {}) => {
    const { size = 9, style = 'normal', color = INK, align = 'left', font = 'helvetica', charSpace } = opts
    doc.setFont(font, style)
    doc.setFontSize(size)
    doc.setTextColor(color[0], color[1], color[2])
    const options = { align, baseline: 'top' }
    if (charSpace) options.charSpace = charSpace
    doc.text(String(str), x, yTop, options)
  }

  const measure = (str, width, size = 9, style = 'normal') => {
    doc.setFont('helvetica', style)
    doc.setFontSize(size)
    return doc.splitTextToSize(String(str), width)
  }

  const addPage = () => {
    doc.addPage()
    doc.setFillColor(ACCENT[0], ACCENT[1], ACCENT[2])
    doc.rect(PAGE.margin, 12, 10, 1.1, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(8)
    doc.setTextColor(INK[0], INK[1], INK[2])
    doc.text('Fortexa scan report', PAGE.margin, 17, { baseline: 'top' })
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(MUTED[0], MUTED[1], MUTED[2])
    doc.text(String(scan.id), PAGE.w - PAGE.margin, 17, { baseline: 'top', align: 'right' })
    doc.setDrawColor(LINE[0], LINE[1], LINE[2])
    doc.setLineWidth(0.2)
    doc.line(PAGE.margin, 21.5, PAGE.w - PAGE.margin, 21.5)
    y = 26
  }

  const ensure = (height) => {
    if (y + height > PAGE.h - PAGE.footer) addPage()
  }

  const para = (str, x, width, opts = {}) => {
    const { size = 9, style = 'normal', color = INK, lh = 4.4 } = opts
    for (const line of measure(str, width, size, style)) {
      ensure(lh)
      text(line, x, y, { size, style, color })
      y += lh
    }
  }

  const heading = (label, reserve = 0) => {
    ensure(6 + reserve)
    y += 3.5
    doc.setFillColor(ACCENT[0], ACCENT[1], ACCENT[2])
    doc.rect(PAGE.margin, y + 0.2, 1.4, 3.6, 'F')
    text(label.toUpperCase(), PAGE.margin + 3.8, y, { size: 10, style: 'bold', charSpace: 0.3 })
    y += 6
  }

  // ── Page 1 header band ─────────────────────────────────────────
  doc.setFillColor(8, 19, 14)
  doc.rect(0, 0, PAGE.w, 32, 'F')
  doc.setFillColor(ACCENT[0], ACCENT[1], ACCENT[2])
  doc.rect(0, 32, PAGE.w, 1.1, 'F')
  text('FORTEXA', PAGE.margin, 8.5, { size: 16, style: 'bold', color: [255, 255, 255], charSpace: 1 })
  text('AI Media Scan Report', PAGE.margin, 20, { size: 9.5, color: [158, 185, 173] })
  text('SCAN ID', PAGE.w - PAGE.margin, 9, { size: 7, style: 'bold', color: [126, 156, 143], align: 'right', charSpace: 0.6 })
  text(scan.id, PAGE.w - PAGE.margin, 13.5, { size: 9, font: 'courier', color: [255, 255, 255], align: 'right' })
  text(fmtDate(scan.created_at), PAGE.w - PAGE.margin, 20, { size: 8.5, color: [158, 185, 173], align: 'right' })
  y = 40

  // ── Verdict panel ──────────────────────────────────────────────
  const panelTop = y
  doc.setFillColor(243, 247, 245)
  doc.roundedRect(PAGE.margin, panelTop, CW, 28, 3, 3, 'F')
  const pillW = 66
  doc.setFillColor(verdict.bg[0], verdict.bg[1], verdict.bg[2])
  doc.roundedRect(PAGE.margin + 5, panelTop + 4.5, pillW, 11, 5.5, 5.5, 'F')
  text(verdict.label, PAGE.margin + 5 + pillW / 2, panelTop + 7.9, { size: 9.5, style: 'bold', color: verdict.fg, align: 'center' })
  text(
    `Risk level: ${report.risk_label || '—'}   ·   Real-photo score: ${realScore != null ? `${realScore}/100` : '—'}`,
    PAGE.margin + 5, panelTop + 19.6, { size: 8.5, color: MUTED },
  )
  text('AI-GENERATION SCORE', PAGE.w - PAGE.margin - 6, panelTop + 5.5, { size: 6.5, style: 'bold', color: MUTED, align: 'right' })
  if (aiScore != null) {
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(22)
    doc.setTextColor(verdict.bar[0], verdict.bar[1], verdict.bar[2])
    doc.text(String(aiScore), PAGE.w - PAGE.margin - 16, panelTop + 9, { align: 'right', baseline: 'top' })
    text('/ 100', PAGE.w - PAGE.margin - 5, panelTop + 21.5, { size: 9.5, style: 'bold', color: MUTED, align: 'right' })
  } else {
    text('unavailable', PAGE.w - PAGE.margin - 5, panelTop + 12, { size: 11, style: 'bold', color: MUTED, align: 'right' })
  }
  y = panelTop + 34

  // ── Score scale: real / inconclusive / AI zones + marker ───────
  const barH = 5
  const zones = [
    [0, 0.4, [187, 247, 208]],
    [0.4, 0.6, [253, 230, 138]],
    [0.6, 1, [254, 202, 202]],
  ]
  for (const [from, to, color] of zones) {
    doc.setFillColor(color[0], color[1], color[2])
    doc.rect(PAGE.margin + CW * from, y, CW * (to - from), barH, 'F')
  }
  doc.setDrawColor(255, 255, 255)
  doc.setLineWidth(0.6)
  doc.line(PAGE.margin + CW * 0.4, y, PAGE.margin + CW * 0.4, y + barH)
  doc.line(PAGE.margin + CW * 0.6, y, PAGE.margin + CW * 0.6, y + barH)
  if (aiScore != null) {
    const prob = Math.min(1, Math.max(0, scan.fake_probability ?? 0.5))
    const markerX = PAGE.margin + Math.min(CW - 1.2, Math.max(1.2, CW * prob))
    doc.setFillColor(31, 41, 55)
    doc.roundedRect(markerX - 1, y - 2, 2, barH + 4, 1, 1, 'F')
  }
  y += barH + 2.6
  text('0', PAGE.margin, y, { size: 7, color: MUTED })
  text('40', PAGE.margin + CW * 0.4, y, { size: 7, color: MUTED, align: 'center' })
  text('60', PAGE.margin + CW * 0.6, y, { size: 7, color: MUTED, align: 'center' })
  text('100', PAGE.margin + CW, y, { size: 7, color: MUTED, align: 'right' })
  y += 3.8
  para(
    'At or above 60 the classifier favors AI-generated; at or below 40 it favors real; in between the result is inconclusive. The score is a model output, not calibrated confidence.',
    PAGE.margin, CW, { size: 7.5, color: MUTED, lh: 3.6 },
  )
  y += 4

  // ── Summary ────────────────────────────────────────────────────
  if (report.summary) {
    const lines = measure(report.summary, CW - 12, 9.5, 'normal')
    const boxH = 7 + lines.length * 4.6
    ensure(boxH + 4)
    doc.setFillColor(238, 245, 241)
    doc.roundedRect(PAGE.margin, y, CW, boxH, 2.5, 2.5, 'F')
    doc.setFillColor(ACCENT[0], ACCENT[1], ACCENT[2])
    doc.rect(PAGE.margin, y + 2, 1.2, boxH - 4, 'F')
    let ty = y + 3.5
    for (const line of lines) {
      text(line, PAGE.margin + 5.5, ty, { size: 9.5 })
      ty += 4.6
    }
    y += boxH + 5
  }

  // ── Media & analysis ───────────────────────────────────────────
  heading('Media & analysis', 36)
  const detailRows = [
    ['File', scan.filename],
    ['Media type', isVideo ? 'Video' : 'Image'],
    ['File size', fmtSize(scan.file_size)],
    ['Model', scan.model_used],
    ['Method', scan.method],
    ['Analysis time', scan.duration_ms != null ? `${(scan.duration_ms / 1000).toFixed(1)} s` : '—'],
    ['Scanned at', fmtDate(scan.created_at)],
    ...(isVideo ? [
      ['Frames sampled', report.analyzed_frames ?? '—'],
      ['Video length', report.duration_seconds != null ? `${report.duration_seconds} s` : '—'],
    ] : []),
  ]
  const drawDetails = (x, width, rows, startY) => {
    let ty = startY
    for (const [label, value] of rows) {
      text(label, x, ty, { size: 8.5, color: MUTED })
      const lines = measure(value ?? '—', width - 34, 8.5, 'bold')
      lines.forEach((line, index) => text(line, x + 34, ty + index * 4.2, { size: 8.5, style: 'bold' }))
      ty = Math.max(ty + 6, ty + lines.length * 4.3 + 1.3)
    }
    return ty
  }
  const half = Math.ceil(detailRows.length / 2)
  const detailsTop = y
  const leftEnd = drawDetails(PAGE.margin, 84, detailRows.slice(0, half), detailsTop)
  const rightEnd = drawDetails(PAGE.margin + 98, 84, detailRows.slice(half), detailsTop)
  y = Math.max(leftEnd, rightEnd) + 2

  const images = preview
    ? [{ ...preview, caption: isVideo ? 'Sampled frame (thumbnail)' : 'Original image' }]
    : []
  if (images.length) {
    const gap = 8
    const boxW = (CW - gap * (images.length - 1)) / images.length
    const maxH = 56
    const sizes = images.map((image) => {
      const ratio = image.width / image.height
      let drawW = boxW
      let drawH = boxW / ratio
      if (drawH > maxH) {
        drawH = maxH
        drawW = maxH * ratio
      }
      return { drawW, drawH }
    })
    const rowH = Math.max(...sizes.map((size) => size.drawH))
    ensure(rowH + 9)
    const rowTop = y
    images.forEach((image, index) => {
      const x = PAGE.margin + index * (boxW + gap)
      const { drawW, drawH } = sizes[index]
      const imageX = x + (boxW - drawW) / 2
      doc.addImage(image.dataUrl, 'JPEG', imageX, rowTop, drawW, drawH)
      doc.setDrawColor(LINE[0], LINE[1], LINE[2])
      doc.setLineWidth(0.2)
      doc.rect(imageX, rowTop, drawW, drawH, 'S')
      text(image.caption, x + boxW / 2, rowTop + rowH + 2, { size: 7, color: MUTED, align: 'center' })
    })
    y = rowTop + rowH + 8
  }

  // ── Diagnostic signals ─────────────────────────────────────────
  const signals = report.signals || []
  if (signals.length) {
    heading('Diagnostic signals', 14)
    const colGap = 8
    const colW = (CW - colGap) / 2
    const rowH = 12.5
    for (let i = 0; i < signals.length; i += 2) {
      ensure(rowH)
      const rowTop = y
      for (let j = 0; j < 2 && i + j < signals.length; j += 1) {
        const signal = signals[i + j]
        const x = PAGE.margin + j * (colW + colGap)
        const score = Math.min(1, Math.max(0, signal.score ?? 0))
        const statusColor = signal.status === 'suspicious'
          ? [220, 38, 38]
          : signal.status === 'normal' ? [5, 150, 105] : [217, 119, 6]
        text(signal.label, x, rowTop, { size: 8.5, style: 'bold' })
        text(`${Math.round(score * 100)}% · ${signal.status}`, x + colW, rowTop, { size: 8, style: 'bold', color: statusColor, align: 'right' })
        doc.setFillColor(TRACK[0], TRACK[1], TRACK[2])
        doc.roundedRect(x, rowTop + 4.6, colW, 2.6, 1.3, 1.3, 'F')
        const fill = score >= 0.6 ? [220, 38, 38] : score <= 0.4 ? [16, 185, 129] : [245, 158, 11]
        doc.setFillColor(fill[0], fill[1], fill[2])
        doc.roundedRect(x, rowTop + 4.6, Math.max(2.6, colW * score), 2.6, 1.3, 1.3, 'F')
      }
      y = rowTop + rowH
    }
    para('Supporting diagnostics only; they never determine the verdict.', PAGE.margin, CW, { size: 7.5, color: MUTED, lh: 3.6 })
    y += 4
  }

  // ── Frame timeline (video) ─────────────────────────────────────
  const timeline = report.timeline || []
  if (isVideo && timeline.length) {
    heading('Frame timeline', 26)
    const count = timeline.length
    let gap = 1.4
    let barW = (CW - gap * (count - 1)) / count
    if (barW < 1.8) {
      gap = 0.5
      barW = (CW - gap * (count - 1)) / count
    }
    barW = Math.max(barW, 1.2)
    const totalW = barW * count + gap * (count - 1)
    const startX = PAGE.margin + (CW - totalW) / 2
    const barH = 13
    const top = y
    timeline.forEach((entry, index) => {
      const classified = entry.classified !== false
      const prob = entry.fake_probability ?? 0.5
      const color = !classified
        ? [203, 213, 225]
        : prob >= 0.6 ? [220, 38, 38] : prob <= 0.4 ? [16, 185, 129] : [245, 158, 11]
      doc.setFillColor(color[0], color[1], color[2])
      const radius = Math.min(1.2, barW / 3)
      doc.roundedRect(startX + index * (barW + gap), top, barW, barH, radius, radius, 'F')
    })
    const maxLabels = Math.max(4, Math.floor(CW / 16))
    const step = Math.max(1, Math.ceil(count / maxLabels))
    for (let i = 0; i < count; i += step) {
      text(`${timeline[i].time}s`, startX + i * (barW + gap) + barW / 2, top + barH + 1.8, { size: 6.5, color: MUTED, align: 'center' })
    }
    y = top + barH + 7
    para(
      'Each bar is one sampled frame: red favors AI-generated, green favors real, amber is inconclusive, grey means the frame could not be classified.',
      PAGE.margin, CW, { size: 7.5, color: MUTED, lh: 3.6 },
    )
    y += 4
  }

  // ── Notes & limitations ────────────────────────────────────────
  const evaluation = report.model_evaluation || {}
  const metrics = evaluation.test_metrics || {}
  const warnings = report.warnings || []
  const notes = [...warnings]
  if (evaluation.evaluation_scope) notes.push(`Model evaluation scope: ${evaluation.evaluation_scope}`)
  const nestedMetrics = Object.values(metrics).filter((entry) => entry && typeof entry === 'object' && entry.accuracy != null)
  const videoMetrics = (metrics.clean?.accuracy != null ? metrics.clean : nestedMetrics[0]) || null
  if (!isVideo && metrics.accuracy != null) {
    const count = metrics.samples ?? metrics.images ?? metrics.examples
    notes.push(`Small-study image test: ${(metrics.accuracy * 100).toFixed(1)}%${count ? ` on ${count} images` : ''}. Not measured accuracy across all generators or videos.`)
  } else if (isVideo && videoMetrics) {
    const count = videoMetrics.samples ?? videoMetrics.examples ?? videoMetrics.clips ?? videoMetrics.images
    notes.push(`Small-study video test (visual only): ${(videoMetrics.accuracy * 100).toFixed(1)}%${count ? ` on ${count} clips` : ''}. Audio and unseen generators are not covered.`)
  }
  notes.push('Compression alone does not make a photo AI-generated. This automated screening result is not proof of authenticity.')
  const noteLines = []
  for (const note of notes) {
    measure(note, CW - 12, 8, 'normal').forEach((line, index) => {
      noteLines.push(index === 0 ? `•  ${line}` : `    ${line}`)
    })
  }
  const boxH = 7.5 + noteLines.length * 4.3
  heading('Notes & limitations', boxH + 6)
  doc.setFillColor(246, 248, 247)
  doc.roundedRect(PAGE.margin, y, CW, boxH, 2.5, 2.5, 'F')
  let ty = y + 4
  for (const line of noteLines) {
    text(line, PAGE.margin + 5, ty, { size: 8, color: NOTE })
    ty += 4.3
  }
  y += boxH + 5
  ensure(6)
  text(`Report generated ${fmtDate(new Date().toISOString())} · fortexa-ai-demo.vercel.app`, PAGE.margin, y, { size: 7.5, color: MUTED })

  // ── Footers ────────────────────────────────────────────────────
  const pages = doc.getNumberOfPages()
  for (let page = 1; page <= pages; page += 1) {
    doc.setPage(page)
    doc.setDrawColor(LINE[0], LINE[1], LINE[2])
    doc.setLineWidth(0.2)
    doc.line(PAGE.margin, PAGE.h - 13, PAGE.w - PAGE.margin, PAGE.h - 13)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(MUTED[0], MUTED[1], MUTED[2])
    doc.text('Fortexa — automated screening result, not proof of authenticity.', PAGE.margin, PAGE.h - 8.5, { baseline: 'top' })
    doc.text(`Page ${page} of ${pages}`, PAGE.w - PAGE.margin, PAGE.h - 8.5, { baseline: 'top', align: 'right' })
  }

  doc.save(`fortexa-report-${scan.id}.pdf`)
}
