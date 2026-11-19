# Policy 02: Security, DSGVO & Zero-Trust IAM

## Scope
Gilt für sämtliche produktiven Datenverarbeitungs- und Agenten-Workloads in der EU.

## Vorgaben
1. **Datenresidenz EU:** Personenbezogene oder regulierte Kundendaten müssen in europäischen GCP-Regionen (bevorzugt `europe-west3` Frankfurt oder `europe-west1`/`europe-west4`) gespeichert und verarbeitet werden.
2. **Verschlüsselung & Transport:** Durchgängige Verschlüsselung im Ruhezustand (CMEK/Google-managed) und im Transit (mindestens TLS 1.2+). Forderungen nach unverschlüsselten Verbindungen oder Deaktivierung von Audit-Logs sind unzulässig (**Security Waiver erforderlich**).
3. **Zero Trust & Least Privilege:** Service-to-Service-Kommunikation zwischen internen Microservices muss über dedizierte Service Accounts (`sa-agent`, `sa-mcp`, `sa-showcase-ui`), IAM `roles/run.invoker` und OIDC Identity Tokens erfolgen. Gemeinsamer Root-Zugriff ohne Nachvollziehbarkeit ist strikt untersagt.
4. **Compliance-Standard:** Architekturen orientieren sich an ISO/IEC 27001, Cloud Audit Logging und OpenTelemetry Observability.
