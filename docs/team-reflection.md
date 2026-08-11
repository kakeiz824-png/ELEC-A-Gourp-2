# Team Reflection — M3


This reflection covers the M3 milestone of the Shelf Life project. We used Codex, ChatGPT, and Claude Code heavily for implementation, testing, documentation, and review-feedback remediation, and those interactions are logged in the AI usage log. The sections below describe where the AI genuinely helped, where it struggled, what surprised us, and what we would change about our approach.

## What AI did well
AI did well at implementing author search and paging. The Title/Author selector and paged results let users search for an author like J. K. Rowling and page through all 431 matches, and a book from any page can be added. Doing this from scratch would have taken us much longer.
AI also did well on the final cover fix. After the first attempt failed, it helped us find the root cause -- Open Library returns 1x1 transparent images for missing covers -- and implement the fallback that detects those images and shows the NO COVER placeholder, together with a regression test. The fix passed both the browser check and the test suite. AI also saved us a lot of time with documentation: it updated the README, organized the AI usage log, and wrote the MCP connection notes, all cross-checked against the actual code and tests.
AI was also very effective at processing review feedback. For the five findings we received, it analysed each one, wrote a failing test first, and then implemented the fix, which kept the suite at 173 passing tests without regressions. It also organised the whole response in REVIEW-RESPONSE.md so nothing was missed.

## Where AI struggled
AI struggled with the cover fix at first: the first version looked correct, but blank covers still appeared because Open Library returns 1x1 transparent images instead of an error. We only found this by testing manually, and the fix had to be redone. AI also produced MCP tools that leaked internal exception text to AI clients (Item 4 in our review response); a human code review caught this and we fixed it.
AI also struggled when we asked it to infer whether a search was a title or an author. It tried that twice and both times failed -- for example, "Dune" is both a novel and a real author's surname, and "Harry Potter" is both a series and a legal historian's name -- so we changed the design and let the user choose explicitly with a Title/Author selector (recorded in DESIGN.md section 7.6). AI could not help with deployment or environment problems either: the Render deploy was blocked by account permissions, and no amount of AI assistance could replace having the right teammate with access available.
AI could also write confident but wrong facts: test counts, pull request numbers, and documentation descriptions sometimes had to be corrected by hand after checking them one by one.

## What surprised you
What surprised us most was how confidently AI can produce wrong results. The first cover fix and the Artifact B test suite both looked completely normal and were delivered with confidence, but were actually broken -- we only noticed by testing. We did not expect that.
Another surprise was how much better AI output became once we gave it proper project context. After we maintained CLAUDE.md and DESIGN.md, the AI's suggestions were noticeably more accurate and we went down far fewer wrong paths.
We were also surprised by how fast AI could deliver a complete feature. Author search, paging, and their tests were done in a few days, which would have taken us much longer by hand.

## What you would do differently
If we started over, we would maintain CLAUDE.md and DESIGN.md from day one and keep them up to date, so AI tools understand the project from the start. A lot of the time we spent explaining context and correcting misunderstandings could have been avoided.
Every AI output should go through a verification checklist before we accept it: run the tests, read the diff, and exercise the feature manually, instead of trusting the result. We would also schedule the documents that must be written by the team (the retrospective, the reflection, and the AI usage log) much earlier, so we were not reconstructing them from memory right before the deadline.
We would start with test-first development and small commits from the beginning, testing as we went instead of piling up features and testing them all at the end. And we would deploy earlier and assign account permissions at the start, so critical steps did not depend on one person being available at the last minute.

## Overall

Overall, AI-augmented development gave us a large speed advantage, but it worked only because we planned first, verified every output, and kept the human responsibility for quality. The combination of small steps, tests, and honest documentation is what we will carry into our next project.
