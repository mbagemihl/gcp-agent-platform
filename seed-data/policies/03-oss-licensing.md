# Policy 03: Open-Source-Lizenzen & Intellectual Property (IP)

## Scope
Gilt für sämtliche Software-Artefakte, Frameworks, Container-Images und Kundenliefergegenstände.

## Vorgaben
1. **Freigegebene permissive Lizenzen:** Für eigene Entwicklungen und integrierte Bibliotheken sind permissive Lizenzen wie **Apache-2.0**, **MIT** und **BSD-3-Clause** standardmäßig freigegeben.
2. **Verbot viraler Copyleft-Lizenzen:** Verpflichtungen zur Übergabe oder Lizenzierung eigener Plattform-Komponenten unter viralen Copyleft-Lizenzen wie **AGPL-3.0** oder **GPLv3** sind wegen IP-Kontaminationsrisiken strikt untersagt (**Harter Blocker / No-Go**, Risiko-Aufschlag +32).
3. **Container Security:** Alle Container-Images werden automatisiert im CI/CD per Trivy auf `HIGH`/`CRITICAL` Schwachstellen gescannt und laufen als Non-Root-User.
