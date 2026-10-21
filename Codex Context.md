# Codex Context

## UI finish · 21 October 2026

- Repository: FightaHackathon/lannpya-ai. Continue `claude/project-thread-gcp93k`; PR target is `prototype`.
- Read [[HANDOFF-UI]] first. Signboard direction remains pinned: Navy, Cream ground, Saffron for action, hairline edges. [[PRODUCT]] records the users and workflow constraints.
- Secondary dispatcher pages now use working sheets, grouped fields, plain route/status wording, and original-chat vs parsed-field previews. Dialogs use specific action copy; rider dialogs put draft Burmese first. Workflow commands, form fields and action hooks are preserved.
- Rider night mode includes inputs, dialogs, queue rows, map labels and the prototype bar. Only lane counts animate (240ms); other transitions are immediate. Static shell version is 0.8.1.
- [[DESIGN]] and `.impeccable/design.json` describe the built system. Impeccable launcher was unavailable (engine absent, cache write blocked), so context and craft guidance were read directly.
- [[BURMESE-REVIEW]] lists 49 distinct authored Burmese UI runs. The owner volunteered to review; native approval is still pending. Keep the PR draft until the approved source commit is recorded.
- Validation: `npm test` passes all 93; `npm run check` passes. Fixed pre-existing Windows CRLF import stripping in `api-workspace.test.mjs`. Browser QA covers desktop/tablet/390px, paste preview, buyer verification, rider night delivery and reduced motion. Evidence and isolated Emil route prototypes are outside the repo in the parent workspace.
- No `screens` directory exists on the supplied branch; fresh synthetic-data screenshots were captured locally. Independent review found a remaining buyer-pin transition; removed it to match the motion rule.

[[PRODUCT]] · [[HANDOFF-UI]] · [[DESIGN]] · [[BURMESE-REVIEW]]
