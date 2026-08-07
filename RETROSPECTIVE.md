# Team Retrospective — M3

*Target: approximately 400-600 words. Must be written in your own words; an AI-generated
retrospective is an academic integrity violation.*

This retrospective covers the M3 milestone of the Shelf Life project: shipping the deployed reading tracker, acting on cross-team review feedback, and preparing the final documentation and demo. It records what we would do differently, what hurt our progress, what we would keep, and the most important lesson we take away.

## Start
If we started over, we would test more comprehensively from earlier on, instead of testing only once the framework was nearly complete -- at which point the results still required major changes.
We would also deploy much earlier, so environment and deployment problems surfaced while there was still time to fix them. And we would assign roles and account access at the start, so critical steps like deployment did not depend on one person being available at the last minute.

## Stop
We relied too much on a single person: deployment could only be triggered by one teammate, so when that person was unavailable, the whole team was blocked.
We should also stop piling up features before testing them -- testing only once the framework was nearly complete meant the results still required major changes. And we should stop accepting AI output without verifying it: the first cover fix looked correct but was actually broken, and only manual testing caught it.

## Continue
We should keep planning before acting: for each task we agreed on the execution plan first and only started after approval, which saved us from going down wrong paths.
We should keep making small commits: one change per branch and per pull request, which kept merges clean and made problems easy to roll back. We should also keep writing tests first (test-driven development): writing a failing test before the implementation caught bugs early, and our suite grew from 38 to 173 passing tests without regressions.

## Most important lesson
AI output must not be trusted blindly -- it has to be verified. The first cover fix looked correct but still showed blank covers (the 1x1 transparent-image case), and in Artifact B the AI claimed all tests passed when they were mostly vacuous. AI is fast, but the final responsibility is human.
AI is an accelerator, not a replacement: it can write code quickly, but the final responsibility for quality stays with the team, which is why every AI contribution has to be verified and logged. Looking back, the biggest takeaway of the whole project is that planning first, working in small steps, and verifying constantly became habits that made our work predictable and reliable.