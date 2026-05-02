# Diagrama de Arquitectura del Research

## Flujo Principal de Investigación (Deep Research)

```mermaid
flowchart TB
    subgraph Entry["Entrada"]
        Q["Usuario: query + target_technology + depth + breadth"]
    end

    subgraph Phase1["Fase 1: Preparación"]
        PE["PromptEngineeringService.improve_query()"]
        PL["PlanningService.create_research_plan()"]
        Q --> PE
        PE --> PL
    end

    subgraph Phase2["Fase 2: Planificación (3 ramas distintas)"]
        direction TB
        PL -->|"Genera"| BRA["Branch A: Técnico"]
        PL -->|"Genera"| BRB["Branch B: Comercial"]
        PL -->|"Genera"| BRC["Branch C: Riesgo/Futuro"]

        BRA -->|"queries"| QA1["specs, benchmarks, arquitectura"]
        BRB -->|"queries"| QA2["pricing, vendors, adopción"]
        BRC -->|"queries"| QA3["CVEs, deprecación, alternativas, roadmap"]
    end

    subgraph Phase3["Fase 3: Búsqueda Web + Análisis + Embedding (por iteración)"]
        direction TB

        subgraph LoopA["Branch A: Loop iterativo depth veces"]
            direction TB
            A1["Query N"]
            A2["WebSearch:<br/>Gemini + google_search nativo"]
            A3["ResearchAnalysis:<br/>Gemma 4 26B review"]
            A4["EmbeddingService:<br/>vector + cosine_similarity<br/>con iteraciones previas"]
            A5{"needs_follow_up?"}
            A6["next_query generado"]
            A1 --> A2 --> A3 --> A4 --> A5
            A5 -->|"Sí + depth < max"| A6
            A6 --> A1
            A5 -->|"No"| ADONE["Acumula learnings + URLs"]
        end

        subgraph LoopB["Branch B: Loop iterativo depth veces"]
            direction TB
            B1["Query N"]
            B2["WebSearch:<br/>Mistral + web_search nativo"]
            B3["ResearchAnalysis:<br/>Mistral Large review"]
            B4["EmbeddingService:<br/>vector + cosine_similarity<br/>con iteraciones previas"]
            B5{"needs_follow_up?"}
            B6["next_query generado"]
            B1 --> B2 --> B3 --> B4 --> B5
            B5 -->|"Sí + depth < max"| B6
            B6 --> B1
            B5 -->|"No"| BDONE["Acumula learnings + URLs"]
        end

        subgraph LoopC["Branch C: Loop iterativo depth veces"]
            direction TB
            C1["Query N"]
            C2["SearchRouter:<br/>Tavily/Exa/Serper<br/>(según query_type)"]
            C2B["OpenRouter:<br/>síntesis de resultados<br/>Claude/Gemini Pro"]
            C3["ResearchAnalysis:<br/>OpenRouter review"]
            C4["EmbeddingService:<br/>vector + cosine_similarity<br/>con iteraciones previas"]
            C5{"needs_follow_up?"}
            C6["next_query generado"]
            C1 --> C2 --> C2B --> C3 --> C4 --> C5
            C5 -->|"Sí + depth < max"| C6
            C6 --> C1
            C5 -->|"No"| CDONE["Acumula learnings + URLs"]
        end
    end

    subgraph Phase4["Fase 4: Grafo Semántico de Embeddings"]
        direction TB
        EM1["Cada iteración genera EmbeddingArtifact"]
        EM2["Relations: cosine_similarity > 0.82<br/>contra embeddings previos"]
        EM3["Grafo: embedding_id → target_embedding_id<br/>con peso similarity"]
        EM1 --> EM2 --> EM3
    end

    subgraph Phase5["Fase 5: Síntesis"]
        SYN["SynthesizerService<br/>synthesize_plan_results()<br/>Gemini 3 Flash Preview"]
    end

    subgraph Output["Salida"]
        RES["ResearchExecutionResult"]
        RPT["report_markdown"]
        META["stage_context + source_urls + learnings + embeddings[]"]
    end

    %% Conexiones de flujo
    QA1 --> LoopA
    QA2 --> LoopB
    QA3 --> LoopC

    ADONE & BDONE & CDONE --> EM3
    EM3 --> SYN
    SYN --> RES
    RES --> RPT
    RES --> META

    %% Fallbacks
    A2 -.->|"falla"| A2B["Fallback: Mistral web_search"]
    C2B -.->|"falla"| C2C["Fallback: NVIDIA minimax-m2.7"]
```

---

## Loop Iterativo por Rama (Detalle)

```mermaid
flowchart TB
    subgraph Input["Input por rama"]
        SEED["seed_queries[]"]
        DEPTH["max_iterations = depth"]
        ACC_L["accumulated_learnings = []"]
        ACC_U["accumulated_urls = []"]
        ACC_E["aggregated_embeddings = []"]
    end

    subgraph Loop["WHILE loop por query + follow-ups"]
        direction TB
        Q1["current_query = seed_query"]
        Q2{"¿Query ya vista?"}
        Q3["search_output = WebSearch()"]
        Q4["analysis = ResearchAnalysis()<br/>→ learnings[], source_urls[],<br/>needs_follow_up, next_query"]
        Q5["embedding = EmbeddingService.embed_iteration()<br/>→ vector + relations[]"]
        Q6["Acumula learnings, URLs, embeddings"]
        Q7{"needs_follow_up?"}
        Q8{"iteration_count < depth?"}
        Q9["current_query = next_query"]
        Q10["BREAK"]

        Q1 --> Q2
        Q2 -->|"No"| Q3
        Q2 -->|"Sí"| Q10
        Q3 --> Q4 --> Q5 --> Q6 --> Q7
        Q7 -->|"Sí"| Q8
        Q7 -->|"No"| Q10
        Q8 -->|"Sí"| Q9
        Q8 -->|"No"| Q10
        Q9 --> Q1
    end

    subgraph Output["Output por rama"]
        R["ResearchBranchResult:<br/>branch_id, provider, learnings[],<br/>source_urls[], iterations,<br/>embeddings[EmbeddingArtifact]"]
    end

    SEED --> Q1
    Q10 --> R
```

---

## Embeddings y Grafo Semántico (Detalle)

```mermaid
flowchart TB
    subgraph PerIteration["Por cada iteración de cada rama"]
        E1["source_text =<br/>'technology=X; query=Y;<br/>learnings=Z'"]
        E2["Gemini Embedding 2:<br/>embed_content(source_text)"]
        E3["vector = [0.12, -0.34, 0.89, ...]"]
    end

    subgraph Relations["Relaciones Semánticas"]
        direction TB
        R1["Para cada embedding previo:<br/>cosine_similarity(current, prev)"]
        R2{"similarity > 0.82?"}
        R3["Crea EmbeddingRelation:<br/>relation_id, source→target,<br/>similarity, reason='semantic_similarity'"]
        R4["Ignora (poco relevante)"]
        R1 --> R2
        R2 -->|"Sí"| R3
        R2 -->|"No"| R4
    end

    subgraph Graph["Grafo Resultante"]
        G1["EmbeddingArtifact 1<br/>iter=1, branch=A"]
        G2["EmbeddingArtifact 2<br/>iter=2, branch=A"]
        G3["EmbeddingArtifact 3<br/>iter=1, branch=B"]
        G4["EmbeddingArtifact 4<br/>iter=2, branch=B"]
        G5["EmbeddingArtifact 5<br/>iter=1, branch=C"]

        G1 -->|"sim=0.91"| G2
        G3 -->|"sim=0.85"| G4
        G1 -.->|"sim=0.75<br/>threshold not met"| G3
    end

    E3 --> Relations
    R3 --> Graph
```

---

## Flujo de Búsqueda por Proveedor

```mermaid
flowchart LR
    subgraph GeminiSearch["Gemini: Búsqueda Nativa"]
        G1["generate_content()"]
        G2["tools=[google_search]"]
        G3["Respuesta con groundingMetadata"]
        G1 --> G2 --> G3
    end

    subgraph MistralSearch["Mistral: Búsqueda Nativa"]
        M1["conversations_start()"]
        M2["tools=[web_search]"]
        M3["Respuesta JSON con learnings + URLs"]
        M1 --> M2 --> M3
    end

    subgraph OpenRouterSearch["OpenRouter: Búsqueda Externa + Síntesis"]
        O1["SearchRouter.search()"]
        O2{"query_type?"}
        O3["Exa: neural search<br/>(papers, docs técnicos)"]
        O4["Serper: Google API<br/>(noticias, market)"]
        O5["Tavily: AI search<br/>(resumen con fuentes)"]
        O6["OpenRouter chat_completions()<br/>síntesis de resultados en prosa"]
        O1 --> O2
        O2 -->|"technical"| O3
        O2 -->|"commercial"| O4
        O2 -->|"overview/risk"| O5
        O3 & O4 & O5 --> O6
    end
```

---

## Estrategia de Queries Diversificadas

```mermaid
flowchart TB
    subgraph Input["Input: target_technology + research_brief"]
        TI["Ej: 'FastAPI'"]
    end

    subgraph BranchA["Branch A: Técnico (Gemini)"]
        A1["FastAPI architecture and standards"]
        A2["FastAPI technical specifications"]
        A3["FastAPI benchmarks and performance"]
    end

    subgraph BranchB["Branch B: Comercial (Mistral)"]
        B1["FastAPI commercial adoption 2025"]
        B2["FastAPI vendor landscape and pricing"]
        B3["FastAPI market share vs competitors"]
    end

    subgraph BranchC["Branch C: Riesgo (OpenRouter)"]
        C1["FastAPI security vulnerabilities CVE"]
        C2["FastAPI deprecation timeline and roadmap"]
        C3["FastAPI alternatives and migration paths"]
    end

    TI --> A1 & A2 & A3
    TI --> B1 & B2 & B3
    TI --> C1 & C2 & C3
```

---

## Anti-Bias Temporal

```mermaid
flowchart LR
    subgraph Old["ANTES (hardcodeado)"]
        O1["Prompt: '...between 2020 and 2024'"]
        O2["Resultado: datos de 2023-2024"]
        O1 --> O2
    end

    subgraph New["AHORA (dinámico)"]
        N1["current_year = datetime.now().year"]
        N2["Prompt: '...current state in 2026, recent 2025-2026'"]
        N3["Resultado: datos actuales"]
        N1 --> N2 --> N3
    end
```

---

## Ejecución Paralela vs Serial

```mermaid
flowchart TB
    subgraph Serial["ANTES: Serial (ramas + iteraciones)"]
        direction LR
        S1A["Branch A iter 1"]
        S1B["Branch A iter 2"]
        S2A["Branch B iter 1"]
        S2B["Branch B iter 2"]
        S3A["Branch C iter 1"]
        S3B["Branch C iter 2"]
        S1A --> S1B --> S2A --> S2B --> S3A --> S3B
        note["Tiempo total = suma de todas las iteraciones"]
    end

    subgraph Parallel["AHORA: Paralelo (asyncio.gather)"]
        direction LR
        subgraph PA["Branch A"]
            P1A["iter 1"]
            P1B["iter 2"]
            P1A --> P1B
        end
        subgraph PB["Branch B"]
            P2A["iter 1"]
            P2B["iter 2"]
            P2A --> P2B
        end
        subgraph PC["Branch C"]
            P3A["iter 1"]
            P3B["iter 2"]
            P3A --> P3B
        end
        PA & PB & PC
        note2["Tiempo total = max(rama A, rama B, rama C)"]
    end
```

---

## Cost Optimization: Cuándo se paga API de búsqueda

```mermaid
flowchart TD
    subgraph Free["GRATIS (nativo del modelo)"]
        G["Gemini google_search"]
        M["Mistral web_search"]
    end

    subgraph Paid["PAGO (SearchRouter)"]
        T["Tavily API"]
        E["Exa API"]
        S["Serper API"]
    end

    subgraph Trigger["Trigger"]
        O["Solo OpenRouter branch usa SearchRouter"]
    end

    G & M -->|"sin costo extra"| OK["✅"]
    O --> T & E & S
    T & E & S -->|"costo API"| PAY["💰 Solo ~33% del tráfico"]
```

---

## Fallback Chain

```mermaid
flowchart LR
    subgraph BranchA["Branch A: Técnico"]
        A1["Gemini 3.1 Flash Lite"]
        A2["HuggingFace DeepSeek-V4"]
        A1 -.->|"fallback"| A2
    end

    subgraph BranchB["Branch B: Comercial"]
        B1["Mistral Small 4"]
        B2["HuggingFace Ling-2.6"]
        B1 -.->|"fallback"| B2
    end

    subgraph BranchC["Branch C: Riesgo"]
        C1["OpenRouter Claude"]
        C2["NVIDIA minimax-m2.7"]
        C3["NVIDIA step-3.5-flash"]
        C1 -.->|"fallback"| C2
        C2 -.->|"fallback"| C3
    end
```

---

## Sequence Diagram Completo (con embeddings + follow-ups)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant PE as PromptEngineering
    participant PL as PlanningService
    participant WS as WebSearchService
    participant RA as ResearchAnalysis
    participant EM as EmbeddingService
    participant SY as SynthesizerService

    U->>PE: raw_query
    PE->>PE: improve_query()<br/>+ anti-bias temporal
    PE->>PL: refined_query
    PL->>PL: create_research_plan()<br/>3 ramas con queries distintas

    par Branch A (Técnico)
        PL->>WS: Query 1A: "FastAPI specs"
        WS->>WS: Gemini + google_search
        WS->>RA: raw_text + URLs
        RA->>RA: Gemma review → learnings[]<br/>needs_follow_up?, next_query
        RA->>EM: embed_iteration() → vector + relations

        alt needs_follow_up AND depth < max
            RA->>WS: Query 2A: "FastAPI benchmarks" (next_query)
            WS->>WS: Gemini + google_search
            WS->>RA: raw_text + URLs
            RA->>RA: Gemma review
            RA->>EM: embed_iteration() → vector + relations
        end
    and Branch B (Comercial)
        PL->>WS: Query 1B: "FastAPI adoption"
        WS->>WS: Mistral + web_search
        WS->>RA: raw_text + URLs
        RA->>RA: Mistral Large review → learnings[]<br/>needs_follow_up?, next_query
        RA->>EM: embed_iteration() → vector + relations

        alt needs_follow_up AND depth < max
            RA->>WS: Query 2B: "FastAPI pricing" (next_query)
            WS->>WS: Mistral + web_search
            WS->>RA: raw_text + URLs
            RA->>RA: Mistral Large review
            RA->>EM: embed_iteration() → vector + relations
        end
    and Branch C (Riesgo)
        PL->>WS: Query 1C: "FastAPI CVEs"
        WS->>WS: SearchRouter → Tavily/Exa/Serper<br/>→ OpenRouter síntesis
        WS->>RA: raw_text + URLs
        RA->>RA: OpenRouter review → learnings[]<br/>needs_follow_up?, next_query
        RA->>EM: embed_iteration() → vector + relations

        alt needs_follow_up AND depth < max
            RA->>WS: Query 2C: "FastAPI alternatives" (next_query)
            WS->>WS: SearchRouter → Tavily
            WS->>RA: raw_text + URLs
            RA->>RA: OpenRouter review
            RA->>EM: embed_iteration() → vector + relations
        end
    end

    EM->>SY: learnings + embeddings[] + relations[] de 3 ramas
    SY->>SY: consolidate()<br/>Gemini 3 Flash Preview
    SY->>U: report_markdown + stage_context + embeddings_graph
```
