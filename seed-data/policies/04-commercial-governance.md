# Policy 04: Kommerzielle Governance & Haftungsbegrenzung

## Scope
Gilt für alle Dienstleistungs-, Werk- und Beratungsverträge im Rahmen von RFPs.

## Vorgaben
1. **Haftungsobergrenze (Liability Cap):** Die vertragliche Gesamthaftung darf maximal das **1-fache des Auftragswertes (1x Contract Value)** betragen.
2. **Verbot unbegrenzter Haftung:** Klauseln mit unbegrenzter Haftung („unlimited liability“ / „unbeschränkte Haftung“) sind nicht versicherbar und stellen einen harten kommerziellen **Blocker / No-Go** dar (Risiko-Aufschlag +28).
3. **SLA-Vertragsstrafen & Timelines:** Pauschale Vertragsstrafen („liquidated damages“) oder unrealistische Go-Live-Fristen (< 48h) lösen eine kommerzielle Eskalation (**Warning**) aus.
4. **Kalkulationsbasis:** Tagessätze und FTE-Verfügbarkeiten müssen verpflichtend über den zentralen **MCP Pricing Server** (`get_role_rates`) abgefragt und jeder Compliance-Report revisionssicher in Firestore protokolliert werden.
