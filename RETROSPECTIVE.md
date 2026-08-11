# Team Retrospective 鈥?M3 Milestone
This retrospective covers the M3 milestone of the Shelf Life project: deploying the reading tracker, acting on cross鈥憈eam review feedback, and preparing final documentation and the demo. It records what we would do differently, what hindered us, what we would keep, and the single most important lesson we take away.

## Start
If we started over, we would maintain project context files like CLAUDE.md and DESIGN.md from day one. That would give AI assistants accurate background information from the very beginning, rather than patching it in midway. This would reduce incorrect generations and repeated corrections caused by missing context.

We would also test more comprehensively and start deployment much earlier. In this milestone, we waited until the framework was nearly complete before running full tests, only to discover major issues that forced extensive rework. Deployment was also left until late in the cycle; environment discrepancies and permission problems surfaced when little time remained. If we had deployed earlier, those risks would have been exposed sooner. Likewise, roles and account access should have been assigned at project kick鈥憃ff, so that critical steps like production deployment wouldn鈥檛 depend on a single person being available鈥攂locking the whole team when that person was unreachable.

## Stop
We relied too heavily on a single point of failure. Deployment permissions were held by only one team member; when that person was unavailable, the entire team was stuck. This single鈥憄erson dependency must be broken in future projects.

We should also stop piling up features before testing them. As mentioned, testing only after the framework was nearly complete led to high鈥慶ost fixes. A better rhythm is to test each module immediately after completion鈥攙erify in small steps, rather than saving everything for a 鈥渂ig bang鈥?

And we must stop accepting AI output without verification. The first cover鈥慺ix code looked perfectly correct, but after deployment it still showed blank covers (the 1脳1 transparent鈥慽mage case). Only manual testing caught it. Similarly, in Artifact B, the AI claimed all tests passed, but those tests were mostly vacuous鈥攖hey didn鈥檛 actually exercise the logic. We cannot take AI鈥檚 conclusions as final answers.

## Continue
Several habits are worth keeping. First, 鈥減lan before acting鈥濃€攚e agreed on an execution plan for each task and only started coding after team approval. This saved us from going down many wrong paths. Second, 鈥渟mall commits鈥濃€攅ach branch solved one problem and each pull request contained a single change, keeping merges clean and rollbacks easy. Third, test鈥慸riven development鈥攚riting a failing test first and then implementing to make it pass grew our test suite from 38 to 173 passing tests without regressions, largely thanks to TDD.

In addition, every piece of AI output should go through a verification checklist: run tests, read the diff carefully, and manually walk through the core flow. This adds some immediate overhead, but drastically reduces rework later鈥攕o we should keep doing it.

## Most important lesson
The single biggest takeaway from the entire project is that AI is an accelerator, not a replacement. It can generate code and documentation quickly, but the ultimate responsibility for quality always rests with the team. AI output must be verified鈥攚hat looks correct may not actually be correct, as the cover鈥慺ix case showed. Human judgment must be the last line of defence, and every AI contribution should be logged for traceability.

More broadly, the habits we built鈥攑lanning first, iterating in small steps, and constantly verifying鈥攑roved to be the foundation that made our work predictable and reliable. Without these habits, even the fastest AI would only create chaos. With them, AI became a genuine efficiency booster. Whether or not we continue using AI in the future, this working style will keep us on a steadier path.


