# Team Reflection — M3

*Target: approximately 800-1000 words. Must be written in your own words; an AI-generated
reflection is an academic integrity violation. Reference specific interactions from the
AI Usage Log.*

## What AI did well
AI did well at implementing author search and paging. The Title/Author selector and paged results let users search for an author like J. K. Rowling and page through all 431 matches, and a book from any page can be added. Doing this from scratch would have taken us much longer.

## Where AI struggled
AI struggled with the cover fix at first: the first version looked correct, but blank covers still appeared because Open Library returns 1x1 transparent images instead of an error. We only found this by testing manually, and the fix had to be redone. AI also produced MCP tools that leaked internal exception text to AI clients (Item 4 in our review response); a human code review caught this and we fixed it.

## What surprised you
What surprised us most was how confidently AI can produce wrong results. The first cover fix and the Artifact B test suite both looked completely normal and were delivered with confidence, but were actually broken -- we only noticed by testing. We did not expect that.

## What you would do differently
If we started over, we would maintain CLAUDE.md and DESIGN.md from day one and keep them up to date, so AI tools understand the project from the start. A lot of the time we spent explaining context and correcting misunderstandings could have been avoided.