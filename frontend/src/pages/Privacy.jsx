import { Link } from 'react-router-dom'
import { ArrowLeft, ShieldCheck } from 'lucide-react'
import Logo from '../components/layout/Logo'

const LAST_UPDATED = 'August 25, 2026'

const sections = [
  {
    title: '1. Overview',
    body: [
      'This Privacy Policy explains how Fortexa ("we", "us", "the Service") handles information when you upload media for deepfake analysis. The short version: we collect the absolute minimum needed to run an analysis, we do not sell anything, and we do not build advertising profiles.',
      'This policy applies only to the Fortexa web application and API. It does not cover third-party services you may access through external links.',
    ],
  },
  {
    title: '2. Information We Collect',
    body: ['When you use the Service, the following data is processed:'],
    list: [
      'Uploaded media files (photos or videos) — stored temporarily to perform forensic analysis;',
      'Technical metadata — file name, size, type, and upload timestamp;',
      'Analysis results — verdicts, probability scores, confidence values and generated artifacts such as heatmaps;',
      'Server logs — standard HTTP request logs (IP address, user agent) retained briefly for security and debugging.',
    ],
  },
  {
    title: '3. No Account, No Personal Profile',
    body: [
      'The Service does not require registration. We do not ask for — or store — your name, email address, phone number, payment details or government identifiers. Because no account exists, we cannot link analyses to your identity beyond the temporary server session.',
    ],
  },
  {
    title: '4. How We Use Your Data',
    body: ['Collected data is used strictly to:'],
    list: [
      'Run the deepfake detection pipeline on your uploaded media;',
      'Display the result to you via a unique scan link;',
      'Maintain service security, stability and error diagnostics;',
      'Aggregate anonymous statistics (e.g., total scans performed) that cannot be linked back to any individual.',
    ],
  },
  {
    title: '5. What We NEVER Do',
    body: ['For clarity, the Service never:'],
    list: [
      'Sells, rents or trades your uploads or metadata to any third party;',
      'Uses your media to train machine-learning models without explicit consent;',
      'Shares your files with advertisers, brokers or data-aggregation networks;',
      'Sends you marketing communication (we have no way to contact you — by design).',
    ],
  },
  {
    title: '6. Data Retention & Deletion',
    body: [
      'Uploads and their analysis artifacts are retained only as long as necessary to operate the demonstration environment, after which they are automatically purged from disk. Database records may persist in anonymized form for aggregate statistics.',
      'Because scans are accessed via unguessable unique links and are not tied to any account, deleting your browser history effectively severs your access to past results; residual server copies expire on schedule.',
    ],
  },
  {
    title: '7. Cookies & Tracking',
    body: [
      'The Service does not use tracking cookies, fingerprinting, analytics beacons or cross-site trackers. Only functional browser storage required for the interface to operate is used. No Google Analytics, Meta Pixel or similar third-party scripts are embedded.',
    ],
  },
  {
    title: '8. Security',
    body: [
      'We apply reasonable technical safeguards: files are stored outside the public web root, scan identifiers are cryptographically random, and all traffic between your browser and the API is encrypted in transit over HTTPS when deployed.',
      'That said, no system is perfectly secure. By using the Service you acknowledge that information transmitted over the internet can never be guaranteed 100% secure, and you should not upload highly sensitive media.',
    ],
  },
  {
    title: '9. Children\u2019s Privacy',
    body: [
      'The Service is not directed at children under 13 (or under 16 in the EU). We do not knowingly process personal data of children. If you believe a minor has provided personal information, contact us so it can be removed.',
    ],
  },
  {
    title: '10. Your Rights',
    body: ['Depending on your jurisdiction (including GDPR and India\'s DPDP Act), you may have rights to:'],
    list: [
      'Access the data associated with your activity (scan ID + metadata);',
      'Request erasure of stored uploads and artifacts;',
      'Object to processing at any time simply by discontinuing use of the Service.',
    ],
    bodyAfter: [
      'Since no account is required, most requests can be self-served: stop using the Service and your data expires automatically per Section 6.',
    ],
  },
  {
    title: '11. Changes to This Policy',
    body: [
      'We may update this Privacy Policy from time to time. Material changes will be reflected by the "Last updated" date above. Continued use of the Service constitutes acceptance of the updated policy.',
    ],
  },
  {
    title: '12. Contact Us',
    body: [
      'For any privacy-related questions or data-removal requests, reach out through the institution\'s department office or the contact channels listed in the website footer.',
    ],
  },
]

export default function Privacy() {
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
            <ShieldCheck size={28} className="text-fortexa-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Privacy Policy</h1>
            <p className="mt-1 text-sm text-fortexa-muted">Last updated: {LAST_UPDATED}</p>
          </div>
        </div>

        <div className="card mb-8 border-fortexa-primary/30 bg-fortexa-primary/5 p-5">
          <p className="text-sm leading-relaxed text-fortexa-muted">
            <span className="font-semibold text-fortexa-primary">TL;DR:</span> No sign-up, no
            tracking, no selling data. Your uploads are analyzed, shown back to you, and then
            expire. That&apos;s it.
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
              {s.bodyAfter?.map((p, i) => (
                <p key={`ba-${i}`} className="mt-3 text-sm leading-relaxed text-fortexa-muted">{p}</p>
              ))}
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
