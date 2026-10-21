# Selected components

| Component | Source and reason |
| --- | --- |
| Authoritative backend | main plus preserved local hardening through Prompt 12: parsing, provider boundary, persistence, buyer security, riders, tests and tools |
| Product UI | ZLHantigravity api.html/api-workspace.mjs/styles: actual dispatcher, customer and rider controls |
| Route/cash extensions | Checkpoint lineage, taken from ZLH: physical hub receipt, atomic preparation, departure, cash declarations and counted receipt/closeout |
| AI runtime | Existing Python rules-first/mock provider boundary; no final model selected |
| Optional AI research | mtt's TypeScript parser (also present in ZLH): Gemini REST adapter, recordings, heuristics, tests and browser rules bundle |
| Local credential boundary | Extended guarded dashboard BFF, with role-bound server clients, session/CSRF and native buyer capabilities |
| Demo presentation | Existing functional prototype and all source presentation assets retained separately as prototype.html |

No nested lannpya-ai/backend directory was copied into the final tree. No old backend
replaced the hardened implementation. Shared-ancestor merges preserved NUL guards and
validation; the management schema conflict was resolved explicitly. The destructive direct
checkpoint deletion helper is not wired into the integrated application. Its source is
preserved in the detached review worktree. The old static backend host/multi-port credential
launcher is replaced by one local origin, while its original branch is unchanged.
