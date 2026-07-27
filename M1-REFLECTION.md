\# M1 Reflection



For Milestone 1, our team built the foundation of Shelf Life, a personal reading tracker developed with FastAPI, SQLite, HTML, CSS, and JavaScript. The application allows users to add and view books, move them between the Reading, Finished, and Wishlist shelves, delete books, and save ratings and reviews. For the M1 demonstration, we use a seeded local lookup so that entering a title such as \*The Hobbit\* automatically fills in the author, publication year, ISBN, and cover without depending on an external service.



Our team used ChatGPT and Claude Code throughout the development process. We used them to turn the initial project topic into clearer requirements, plan the data model and API endpoints, organize the project structure, generate implementation ideas, and create tests. We also provided the AI tools with project-specific context through `CLAUDE.md` and `DESIGN.md`. An iterative approach worked better than asking the AI to build the entire application at once: we divided the work into smaller tasks, reviewed each result, and tested it before continuing.



The most successful part of M1 was verification. We ran the automated test suite and confirmed that all 38 tests passed. We also manually tested the main user journey by adding \*The Hobbit\*, checking the automatically filled metadata, saving a five-star review, moving the book from Reading to Finished, and refreshing the page to confirm that the data remained stored. The seeded lookup also made the demonstration reliable without requiring a network connection.



We did not identify a clear case of incorrect AI-generated code that required manual repair during M1. However, human review was still necessary to check that the documentation, data model, API behavior, and implementation were consistent. We also manually resolved local Windows setup issues, including PowerShell script restrictions and pytest temporary-folder permissions. This experience showed us that AI output should not be trusted without testing and human interpretation.



Our main lesson from M1 is that a small, stable, and testable product is more valuable than adding too many features at once. For M2, our team is discussing five possible improvements: a related-books page that recommends three books, category-based browsing, author profiles and complete works, personal accounts with friendships and chatrooms, and an AI-assisted book search and recommendation system. Our likely first priorities are the Open Library MCP integration, related-book recommendations, categories, and author information because they extend the current architecture directly. The social and AI-assistant features require additional security, infrastructure, and evaluation work, so their exact scope will be decided by the team before implementation.

