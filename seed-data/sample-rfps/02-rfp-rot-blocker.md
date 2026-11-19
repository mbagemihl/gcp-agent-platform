# Ausschreibung: Hochsicherheits-Dokumenten-Core (Air-Gapped & Copyleft)

## 1. Betriebsmodell & Infrastruktur-Vorgaben
Die **Behörden-IT-Zentrale** schreibt ein klassifiziertes Dokumentenanalyse-System aus, das unter folgenden zwingenden Bedingungen betrieben werden muss:

- **Striktes On-Premises / Air-Gapped Deployment:** Das Gesamtsystem darf ausschließlich **strictly on-prem / air-gapped** im abgeschotteten Rechenzentrum des Auftraggebers ohne jegliche Cloud-Konnektivität betrieben werden (**kein Cloud-Zugriff / no public cloud**).
- Die Nutzung von Google Cloud Platform (GCP), Cloud Run, Vertex AI oder anderen Managed Cloud APIs ist vertraglich ausgeschlossen.

## 2. Lizenzierung & Quellcode-Übergabe
- Sämtlicher im Projekt erstellter Quellcode sowie alle eingebundenen Agenten- und Orchestrierungs-Module müssen vollständig unter **AGPL-3.0 (viral open source / copyleft)** veröffentlicht und ohne IP-Vorbehalte übertragen werden.

## 3. Kommerzielle & Sicherheitsbedingungen
- **Haftung:** Der Auftragnehmer übernimmt eine **unbegrenzte Haftung (unlimited liability)** für sämtliche direkten Schäden, Folgeschäden und Betriebsunterbrechungen; ergänzend gelten pauschale **Vertragsstrafen (liquidated damages)** bei 48h Go-Live-Verzug.
- **Administration:** Aus Wartungsgründen verlangen lokale Administratoren gemeinsamen **Root-Zugriff (root access)** ohne separates Audit-Logging.
- **Benötigte Rollen:** Cloud Architect, Security Architect, AI Engineer.
