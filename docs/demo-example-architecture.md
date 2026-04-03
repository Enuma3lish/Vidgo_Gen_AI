# Demo Example Architecture

This diagram compares the disabled legacy request-time demo generation path with the current target architecture.

```mermaid
flowchart LR
    subgraph Legacy[Legacy flow now disabled]
        L1[Demo user action] --> L2[Legacy demo generate endpoint or cache miss fallback]
        L2 --> L3[External AI provider call]
        L3 --> L4[Temporary Redis cache with TTL]
        L4 --> L5[Return generated demo]
    end

    subgraph Target[Current backend contract]
        A1[Developer or admin] --> A2[scripts.main_pregenerate or POST /api/v1/admin/generate-demo]
        A2 --> A3[PiAPI / Pollo / A2E by tool]
        A3 --> A4[Material DB approved demo rows]
        A4 --> A5[Redis demo read cache no TTL]

        U1[Demo user opens tool page] --> A6[GET /api/v1/demo/presets/{tool_type}]
        A6 --> A4

        U2[Demo user clicks example] --> A7[POST /api/v1/demo/use-preset]
        A7 --> A5
        A5 --> A4
        A5 --> A8[Return existing watermarked result]
    end

    subgraph Subscriber[Subscriber runtime generation remains]
        S1[Subscriber submits tool request] --> S2[POST /api/v1/tools/* or related endpoint]
        S2 --> S3[External AI provider runtime generation]
        S3 --> S4[Persist user generation and deduct credits]
        S4 --> S5[Return full-quality result]
    end
```

Notes:

- The target backend path no longer generates demo content on request-time cache miss.
- Developers must generate each default example with the real provider API, confirm the output is correct, and store that finished result in Redis before users can access it.
- Redis now acts as a non-expiring read cache for demo examples.
- Material DB remains the durable source of truth for approved examples.
- User expectation is cache-only demo retrieval: query existing example data, never create a new demo output on click.
- Vue demo actions now resolve selected preset IDs through `/api/v1/demo/use-preset`.