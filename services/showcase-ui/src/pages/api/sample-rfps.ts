import fs from 'node:fs/promises';
import path from 'node:path';
import type { APIRoute } from 'astro';

interface SampleRfp {
  id: string;
  title: string;
  badge: 'GREEN' | 'RED';
  label: string;
  content: string;
}

const BUILTIN_SAMPLE_RFPS: SampleRfp[] = [
  {
    id: 'builtin-green-cloud-native',
    title: 'FinTech Data & AI Platform (GCP Cloud-Native)',
    badge: 'GREEN',
    label: 'Grün / Machbar',
    content: `Ausschreibung: Cloud-Native Customer Intelligence Plattform (GCP)

1. Zielsetzung & Architektur
Der Auftraggeber sucht einen Partner für den Aufbau einer KI-gestützten Kundenanalyse-Plattform auf Google Cloud Platform (GCP) in der Region europe-west3 (Frankfurt).
- Compute & Services: Cloud Run, Vertex AI (Gemini 2.5 Flash / Pro), Cloud Firestore und BigQuery.
- Infrastruktur: Bereitstellung reproduzierbar via Terraform und GitHub Actions CI/CD (Workload Identity Federation).

2. Sicherheit, Datenschutz & Lizenzierung
- Vollständige DSGVO-Konformität mit Datenhaltung ausschließlich in europe-west3.
- ISO 27001 orientierte Zero-Trust-IAM-Kontrollen, TLS 1.2+ und Cloud Audit Logging.
- Open-Source-Komponenten unter permissiven Lizenzen (Apache-2.0 / MIT).

3. Kommerzielle Rahmenbedingungen & Team
- Gesuchte Rollen: Cloud Architect, AI Engineer, Data Engineer und DevSecOps Engineer.
- Haftungsbegrenzung auf den einfachen Auftragswert (1x Contract Value).
- Projektstart in 3 Wochen, Laufzeit 6 Monate.`,
  },
  {
    id: 'builtin-red-blocker',
    title: 'Behörden-Core-System (Air-Gapped + AGPL + Unbegrenzte Haftung)',
    badge: 'RED',
    label: 'Rot / Blocker',
    content: `Ausschreibung: Hochsicherheits-Dokumentenanalyse-System (On-Premises Only)

1. Betriebsmodell & Infrastruktur
- Das Gesamtsystem muss zwingend strictly on-prem / air-gapped im Rechenzentrum des Kunden betrieben werden (kein Cloud-Zugriff, no public cloud, keine Cloud-APIs).
- Nutzung von Managed Cloud Services (GCP, Vertex AI, Cloud Run) ist vertraglich ausgeschlossen.

2. Lizenzierung & IP-Vorgaben
- Sämtlicher entwickelter Quellcode sowie verwendete Agent-Frameworks müssen vollständig unter AGPL-3.0 (viral open source / copyleft) an den Kunden übergeben werden.

3. Kommerzielle & Sicherheitsvorgaben
- Der Auftragnehmer übernimmt eine unbegrenzte Haftung (unlimited liability) für sämtliche Folgeschäden.
- Systemadministratoren erhalten gemeinsamen Root-Zugriff (root access) ohne separates Audit Logging.`,
  },
];

async function readDiskSampleRfps(): Promise<SampleRfp[]> {
  const candidates = [
    process.env.STAGE_SAMPLE_RFPS_DIR,
    path.resolve(process.cwd(), '../../seed-data/sample-rfps'),
    path.resolve(process.cwd(), 'seed-data/sample-rfps'),
  ].filter((value): value is string => Boolean(value));

  for (const dir of candidates) {
    try {
      const entries = await fs.readdir(dir);
      const rfpFiles = entries.filter((name) => name.endsWith('.md') || name.endsWith('.txt')).sort();
      if (rfpFiles.length === 0) continue;

      const loaded: SampleRfp[] = [];
      for (const fileName of rfpFiles) {
        const content = (await fs.readFile(path.join(dir, fileName), 'utf-8')).trim();
        if (!content) continue;
        const lower = `${fileName} ${content}`.toLowerCase();
        const isRed =
          lower.includes('rot') ||
          lower.includes('blocker') ||
          lower.includes('agpl') ||
          lower.includes('air-gapped') ||
          lower.includes('unlimited liability');
        loaded.push({
          id: `disk-${fileName}`,
          title: fileName.replace(/\.(md|txt)$/i, '').replace(/[-_]/g, ' '),
          badge: isRed ? 'RED' : 'GREEN',
          label: isRed ? 'Rot / Blocker' : 'Grün / Machbar',
          content,
        });
      }
      if (loaded.length > 0) return loaded;
    } catch {
      // Directory not present in container or local path; fall back to built-in samples
    }
  }
  return [];
}

export const GET: APIRoute = async () => {
  const diskSamples = await readDiskSampleRfps();
  const samples = diskSamples.length > 0 ? diskSamples : BUILTIN_SAMPLE_RFPS;

  return new Response(JSON.stringify({ samples }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
