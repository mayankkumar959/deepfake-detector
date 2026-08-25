import { Link } from 'react-router-dom'
import { ArrowLeft, FileText } from 'lucide-react'
import Logo from '../components/layout/Logo'

const LAST_UPDATED = 'August 25, 2026'

const sections = [
  {
    title: '1. Acceptance of Terms',
    body: [
      'By accessing or using Fortexa ("the Service"), a deepfake detection platform provided for educational and demonstrative purposes as part of a final year academic project, you agree to be bound by these Terms of Service ("Terms"). If you do not agree with any part of these Terms, you must discontinue use of the Service immediately.',
      'These Terms constitute the entire agreement between you and Fortexa regarding your use of the Service and supersede any prior arrangements, whether electronic, verbal, or written.',
    ],
  },
  {
    title: '2. Description of the Service',
    body: [
      'Fortexa provides automated forensic analysis of digital media — including photographs and video files — to estimate the likelihood that the media has been synthetically generated or manipulated ("deepfakes"). The Service combines heuristic signal analysis (error level analysis, frequency-domain inspection, noise inconsistency, blending seam detection and illumination mismatch) with machine-learning inference.',
      'The Service is offered free of charge, without registration, for evaluation, research and demonstration purposes. Uploads are analyzed automatically and no account creation is required.',
    ],
  },
  {
    title: '3. Eligibility & Acceptable Use',
    body: [
      'You may use the Service only if you can form a binding contract, and in compliance with all applicable local, state, national and international laws and regulations.',
      'You agree NOT to use the Service to:',
    ],
    list: [
      'Analyze media that you do not own or lack explicit permission to analyze;',
      'Process content depicting minors in any inappropriate context;',
      'Upload material that is unlawful, defamatory, harassing, or infringes intellectual-property rights;',
      'Attempt to reverse-engineer, overload, scrape or disrupt the Service infrastructure;',
      'Use automated systems (bots, crawlers) to submit bulk requests without prior written consent.',
    ],
  },
  {
    title: '4. Accuracy of Results — Important Disclaimer',
    body: [
      'THE RESULTS PRODUCED BY FORTEXA ARE PROBABILISTIC ESTIMATES AND ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. A verdict, confidence score, or risk classification produced by the Service must never be treated as definitive proof of authenticity or manipulation.',
      'Deepfake detection is an active research area; state-of-the-art detectors — including ours — produce both false positives (authentic media flagged as fake) and false negatives (manipulated media flagged as authentic). You acknowledge that:',
    ],
    list: [
      'Results are intended for research, education and awareness purposes only;',
      'The Service must not be used as sole evidence in legal, employment, insurance, journalistic or disciplinary decisions;',
      'You bear full responsibility for how you interpret and act upon any output from the Service.',
    ],
  },
  {
    title: '5. Uploaded Content & Data Retention',
    body: [
      'Files you upload are stored temporarily on the Service\'s server solely to perform analysis and to display results back to you. By uploading content, you grant Fortexa a limited, non-exclusive, revocable license to process the file for the exclusive purpose of providing the detection result.',
      'We claim no ownership over your uploads. You retain all rights to your media. Analysis artifacts (heatmaps, thumbnails) are derived solely from your file and are accessible only through the unique scan link generated for your upload.',
    ],
  },
  {
    title: '6. Intellectual Property',
    body: [
      'All components of the Service — including source code, models, design, branding, text and graphics — are the property of the project authors and protected by applicable intellectual-property laws. Nothing in these Terms transfers ownership of any intellectual property to you.',
      'You may reference or cite the project for academic purposes with appropriate attribution.',
    ],
  },
  {
    title: '7. Limitation of Liability',
    body: [
      'TO THE MAXIMUM EXTENT PERMITTED BY LAW, IN NO EVENT SHALL THE AUTHORS, CONTRIBUTORS OR AFFILIATED INSTITUTIONS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL OR PUNITIVE DAMAGES — INCLUDING LOSS OF DATA, PROFITS, REPUTATION OR GOODWILL — ARISING FROM YOUR USE OF, OR INABILITY TO USE, THE SERVICE.',
      'The total aggregate liability of Fortexa for any claim relating to the Service shall not exceed the amount you paid to use the Service, which is zero (₹0).',
    ],
  },
  {
    title: '8. Availability & Modification',
    body: [
      'The Service is provided on an experimental basis. We reserve the right to modify, suspend or discontinue any part of the Service at any time without notice. We shall not be liable to you or any third party for any modification, suspension or discontinuance.',
    ],
  },
  {
    title: '9. Governing Law',
    body: [
      'These Terms shall be governed by and construed in accordance with the laws of India, without regard to conflict-of-law provisions. Any dispute arising out of these Terms shall be subject to the exclusive jurisdiction of the courts located in the project institution\'s jurisdiction.',
    ],
  },
  {
    title: '10. Changes to These Terms',
    body: [
      'We may revise these Terms at any time. The current version will always be posted on this page with an updated "Last updated" date. Continued use of the Service after changes constitutes acceptance of the revised Terms.',
    ],
  },
  {
    title: '11. Contact',
    body: [
      'Questions about these Terms may be directed to the project team through the institution\'s department office or via the contact links provided in the website footer.',
    ],
  },
]

export default function Terms() {
  return (
    <div className="min-h-screen bg-fortexa-bg text-fortexa-text">
      <header className="sticky top-0 z-40 border-b border-white/10 bg-fortexa-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-4 lg:px-8">
          <Logo />
          <Link to="/" className="btn-secondary !py-2 !px-4 text-sm">
            <ArrowLeft size={14} /> Back to Scanner
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-12 lg:px-8">
        <div className="mb-10 flex items-center gap-4">
          <div className="rounded-2xl border border-fortexa-primary/20 bg-fortexa-primary/10 p-4">
            <FileText size={28} className="text-fortexa-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Terms of Service</h1>
            <p className="mt-1 text-sm text-fortexa-muted">Last updated: {LAST_UPDATED}</p>
          </div>
        </div>

        <div className="card mb-8 border-fortexa-accent/30 bg-fortexa-accent/5 p-5">
          <p className="text-sm leading-relaxed text-fortexa-muted">
            <span className="font-semibold text-fortexa-accent">TL;DR:</span> Fortexa is a free
            educational tool. Results are probabilistic estimates — never treat them as proof.
            Don&apos;t upload media you don&apos;t have the right to analyze.
          </p>
        </div>

        <div className="space-y-8">
          {sections.map((s) => (
            <section key={s.title} className="glass card">
              <h2 className="mb-3 text-lg font-bold">{s.title}</h2>
              {s.body.map((p, i) => (
                <p key={i} className="mb-3 text-sm leading-relaxed text-fortexa-muted">{p}</p>
              ))}
              {s.list && (
                <ul className="mt-2 space-y-2">
                  {s.list.map((li, i) => (
                    <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-fortexa-muted">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-fortexa-primary" />
                      {li}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>

        <footer className="mt-14 flex flex-col items-center gap-4 border-t border-white/10 pt-8 pb-4 text-center">
          <Logo size="sm" />
          <nav className="flex items-center gap-6 text-sm text-fortexa-muted">
            <Link to="/terms" className="hover:text-white">Terms of Service</Link>
            <Link to="/privacy" className="hover:text-white">Privacy Policy</Link>
            <Link to="/" className="hover:text-white">Scanner</Link>
          </nav>
          <p className="text-xs text-fortexa-muted/60">© {new Date().getFullYear()} Fortexa · Final Year Project</p>
        </footer>
      </main>
    </div>
  )
}
