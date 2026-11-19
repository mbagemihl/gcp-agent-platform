# Policy 01: Enterprise Cloud-First Strategy (GCP)

## Scope
Gilt für alle Kundenprojekte, Architektur-Reviews und Ausschreibungsbewertungen (RFPs).

## Vorgaben
1. **Cloud-First & Managed Services:** Alle neuen Plattformen und KI-Workloads müssen auf verwalteten Google Cloud Platform (GCP)-Services aufbauen (z. B. Cloud Run, GKE, Vertex AI, Cloud Firestore, BigQuery).
2. **Kein reines Air-Gapped / On-Premises Only:** Ausschreibungen, die zwingend ein vollständig vom Internet isoliertes („air-gapped“) oder reines On-Premises-Deployment ohne Nutzung von GCP Managed Services vorschreiben, verstoßen gegen unsere Standard-Lieferarchitektur (**Blocker / No-Go**, Risiko-Aufschlag +38).
3. **Infrastructure as Code:** Bereitstellung erfolgt automatisiert und reproduzierbar via Terraform mit Workload Identity Federation (keyless CI/CD).
