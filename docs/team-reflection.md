# Team Reflection — M3 Milestone

This reflection covers the M3 milestone of the Shelf Life project. We relied heavily on AI tools (Codex, ChatGPT, and Claude Code) for implementation, testing, documentation, and addressing cross‑team review feedback. All interactions are recorded in our AI usage log. The sections below assess where AI truly helped, where it fell short, what caught us off guard, and how we would adjust our approach in the future.

---

## What AI did well

AI excelled at processing and acting on review feedback. We received five findings from the cross‑team review; for each one, the AI analysed the issue, wrote a failing test first, and then implemented a fix that satisfied the test. This kept our test suite at 173 passing tests with no regressions. The AI also organised our entire response in `REVIEW-RESPONSE.md`, structuring it so that every finding was addressed explicitly and nothing slipped through the cracks.

Beyond review remediation, AI was also effective at implementing feature enhancements. The author‑search and paging functionality, for example, was built with AI assistance. Users can now search for an author like J. K. Rowling, page through all 431 matches, and add any book from any page. Doing this from scratch would have taken us substantially longer. The same held for the final cover fix: after our first attempt failed, AI helped us trace the root cause (Open Library returns 1×1 transparent images for missing covers) and implement a fallback that detects those images and shows a “NO COVER” placeholder, together with a regression test. The fix passed both browser validation and the full test suite.

AI also saved us significant time on documentation. It updated the README, maintained the AI usage log, and wrote MCP connection notes — all cross‑checked against actual code and tests. This allowed us to focus more on core development while keeping our documentation consistently up‑to‑date.

---

## Where AI struggled

AI’s struggles were equally instructive. The first cover‑fix attempt looked plausible and even passed initial inspection, but blank covers still appeared in practice because the AI did not anticipate the 1×1 transparent‑image case. Only manual testing uncovered this, forcing a redo. Similarly, when we asked the AI to infer whether a search query was a title or an author, it tried twice and failed both times. For example, “Dune” is both a famous novel and a real author’s surname; “Harry Potter” is both a series title and the name of a legal historian. These ambiguities made automatic inference unreliable, so we changed the design to let users explicitly choose between title and author search (recorded in `DESIGN.md` section 7.6). AI could not reason through these real‑world ambiguities.

Another weakness was in tooling: AI produced MCP tools that leaked internal exception text to AI clients (Item 4 in our review response). A human code review caught this and corrected it. AI also struggled with deployment and environment issues — the Render deployment was blocked by account permissions, and no amount of AI advice could replace having the right teammate with access available.

Moreover, AI occasionally produced confidently wrong statements: test counts, pull‑request numbers, and even some documentation descriptions had to be corrected manually after we verified them one by one. The AI’s confidence often outran its accuracy.

---

## What surprised you

The biggest surprise was the sheer confidence with which AI delivers incorrect results. The first cover fix and the test suite from Artifact B both looked entirely normal and were presented with full assurance, yet both were broken — we only noticed by actually running the tests and manually exercising the features. We did not expect such polished‑looking output to be so fundamentally flawed.

Another positive surprise was how dramatically AI output improved once we provided proper project context. After we maintained `CLAUDE.md` and `DESIGN.md` with accurate, up‑to‑date information, the AI’s suggestions became noticeably more relevant, and we wasted far less time correcting misunderstandings.

We were also surprised by how quickly AI could deliver a complete feature. Author search, paging, and their associated tests were completed in just a few days — a task that would have taken us much longer by hand. The speed was impressive, but it also reinforced the need for careful verification.

---

## What you would do differently

If we started over, we would maintain project‑context files (`CLAUDE.md`, `DESIGN.md`) from day one and keep them continuously updated. Much of the time we spent explaining context and re‑explaining the project structure could have been avoided if AI tools had that information from the start.

Every piece of AI output should go through a mandatory verification checklist before acceptance: run the tests, read the diff carefully, and manually exercise the feature in the browser. We should never trust a result just because it looks plausible.

We would also schedule the documents that must be written by the team (the retrospective, this reflection, and the AI usage log) much earlier in the timeline. Instead of reconstructing them from memory right before the deadline, we would write them incrementally as the project progressed, capturing insights while they were fresh.

Test‑first development and small commits should be adopted from the very beginning. We would test each module as we built it, rather than piling up features and testing everything at the end. This would catch issues earlier and reduce the cost of fixes.

Finally, we would deploy earlier and assign account permissions at project kick‑off, so that critical deployment steps do not depend on a single person being available at the last minute. This would eliminate the blocking delays we experienced.

---

## Overall

Overall, AI‑augmented development gave us a significant speed advantage, but it worked only because we combined it with disciplined practices: planning first, verifying every output, and maintaining human responsibility for quality. The habits we built — small steps, continuous testing, honest documentation, and early verification — are what we will carry forward. AI is a powerful accelerator, but it is not a substitute for human judgment. When used with care, it helps us move faster; when trusted blindly, it leads us astray. This balance is the most valuable lesson of this milestone.