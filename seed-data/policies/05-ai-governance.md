# Policy 05: Enterprise AI & Agentic Governance

## Scope
Gilt für alle LLM-, RAG- und Multi-Agenten-Implementierungen auf Vertex AI.

## Vorgaben
1. **Grounding & RAG:** Unternehmensrichtlinien und geschäftskritische Aussagen müssen über ein zentrales **Vertex AI RAG Corpus** (`text-embedding-005`) geerdet werden.
2. **Modell-Standards:** Produktive Agenten nutzen freigegebene Vertex-AI-Gemini-Modelle (aktuell Gemini 3.x-Familie wie `gemini-3.8-flash` oder `gemini-3.1-pro-preview`) mit strukturiertem Prompting und reproduzierbaren Parametern (`temperature <= 0.2`).
3. **End-to-End Observability:** Jeder Agenten-Durchlauf muss per **OpenTelemetry** instrumentiert werden und Latenzen, Tool-Aufrufe, RAG-Quellen sowie Token-Kosten sowohl im Live-Stream als auch in **Google Cloud Trace** nachweisbar dokumentieren.
