# M1 Reflection

For Milestone 1, our team built the foundation of Shelf Life, a personal reading
tracker using FastAPI, SQLite, HTML, CSS, and JavaScript. Users can add books, organize
them across Reading, Finished, and Wishlist, delete them, and save ratings and reviews.
Our M1 version used the local catalogue in `seed/books.json`, so entering *The Hobbit*
filled in the author, year, ISBN, and cover without depending on the network. This made
our main demonstration predictable and repeatable.

We used ChatGPT and Claude Code to clarify requirements, plan the Book-Review data
model and API endpoints, organize the repository, explore implementation ideas, and
support test creation. The most useful prompting technique was to divide the project
into small tasks and give the AI project-specific context through `CLAUDE.md` and
`DESIGN.md`. Asking for one endpoint, validation rule, or test group at a time produced
results that were easier to understand and review than asking the AI to build the
whole application at once. Clear acceptance criteria also helped us turn requirements
such as the 1-5 rating range and review cascade deletion into tests.

Verification was the strongest part of our M1 process. The M1 snapshot passed 38
automated tests with one deprecation warning. We also manually added *The Hobbit*,
checked its metadata, saved a five-star review, moved it from Reading to Finished, and
refreshed the page to confirm persistence. We did not identify a clear example of
incorrect AI-generated application code that required manual repair. However, human
review was still necessary to compare the documentation with the real data model and
API behavior. During verification, we also handled local Windows problems involving
PowerShell script restrictions, the nested project folder, and pytest temporary-folder
permissions. These issues reminded us to inspect the environment before changing code.

Our main lesson is that AI is most useful when the team gives it a narrow task and then
checks the result with tests, a manual workflow, and a file diff. A small, stable,
testable product was more valuable for M1 than a larger collection of unfinished
features. For M2, we will complete the required Open Library MCP server, mocked MCP
tests, regression testing, and security scan before considering recommendation or
discovery features.
