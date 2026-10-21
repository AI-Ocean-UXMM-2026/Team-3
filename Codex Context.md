# Codex Context

## UI finish · 21 October 2026

- Repository: FightaHackathon/lannpya-ai. Continue `claude/project-thread-gcp93k`; PR target is `prototype`.
- Read [[HANDOFF-UI]] first. Signboard direction remains pinned: Navy, Cream ground, Saffron for action, hairline edges. [[PRODUCT]] records the users and workflow constraints.
- Secondary dispatcher pages now use working sheets, grouped fields, plain route/status wording, and original-chat vs parsed-field previews. Dialogs use specific action copy; rider dialogs put draft Burmese first. Workflow commands, form fields and action hooks are preserved.
- Rider night mode includes inputs, dialogs, queue rows, map labels and the prototype bar. Only lane counts animate (240ms); other transitions are immediate. Static shell version is 0.8.3.
- [[DESIGN]] and `.impeccable/design.json` describe the built system. Impeccable launcher was unavailable (engine absent, cache write blocked), so context and craft guidance were read directly.
- [[BURMESE-REVIEW]] lists 49 distinct authored Burmese UI runs. The owner approved the Burmese in chat on 21 October 2026; see the approved source commit in [[BURMESE-REVIEW]].
- Validation: `npm test` passes all 93; `npm run check` passes. Fixed pre-existing Windows CRLF import stripping in `api-workspace.test.mjs`. Browser QA covers desktop/tablet/390px, paste preview, buyer verification, rider night delivery and reduced motion. Evidence and isolated Emil route prototypes are outside the repo in the parent workspace.
- No `screens` directory exists on the supplied branch; fresh synthetic-data screenshots were captured locally. Independent review found a remaining buyer-pin transition; removed it to match the motion rule.

[[PRODUCT]] · [[HANDOFF-UI]] · [[DESIGN]] · [[BURMESE-REVIEW]]

## Clutter refinement · 21 October 2026

- The owner explicitly prefers the original screenshot's Navy/Saffron lane fills, Paper cards, border colours and logo treatment. Preserve that design; avoid replacing it with a flat or colourless layout.
- Increased group spacing, card padding and line height; reduced weight on secondary text. Removed visible repeated lane hints and card dates while retaining accessible descriptions and order IDs.
- Prototype diagnostics are under Demo tools; role links and offline/storage warnings stay visible. The order check keeps every field and panel in its original position; metadata gets its own line and status copy is shorter. The rider design is unchanged apart from shared text spacing.
- Full root suite: 93/93 passed. Independent focused review found no actionable functional or accessibility findings in the final conservative refinement. Browser QA passed 30 page/viewport checks, six enlarged-text views and the rider cash/close-out flows. The owner subsequently approved the Burmese; see [[BURMESE-REVIEW]].

## Selected Inline navigation · 21 October 2026

- Owner selected Inline from the three isolated navigation prototypes and asked for the LannPya text beside the mobile logo in the empty header space.
- Applied Inline spacing and retained the complete Cream/Saffron wordmark next to the existing mark on phones. Page structure, border colours and workflow controls stay unchanged. Static shell: 0.8.3.
- Owner approved Burmese against source commit `6b800c48741ec3973378253a1b0b92ae573167d6`; the navigation/mobile change does not alter Burmese copy. The PR can move from draft to ready after verification; do not merge without a request.
- Remove the isolated navigation picker after promotion as required by emil-prototype. Preserve QA screenshots outside the repository.
