# Agent instructions for code review in Portale-von-Molthar

1. Read the AGENTS.md to see the rules all developers should follow.
2. Provide list of items, where each item starts in a new line with "* [ ]" to create a box for the assignee to tick.
3. Start your review by stating the SHA1 hash of the commit that was reviewed.
4. Each item contains additional information to easily locate the problem, e.g., by stating file or files and the line numbers.
5. Point out all violations of Google-docstring formatting in such an itemized list.
6. Code issues you should identify are algorithm or syntax bugs, non pythonic coding style, inconsistent changes when refactoring. Issues must be related to the current diff.
7. For small merge requests with less than 250 lines diff, state the top-3 issues besides docstring formatting. Itemized list with as described in 2) with "* [ ]"; do not number despite top-3.
8. For large merge requests with more than 250 lines diff, state the top-5 issues besides docstring formatting. Itemized list with as described in 2) with "* [ ]"; do not number despite top-5.
9. Write each identified issue clearly and specifically. Explain what is wrong, why it matters, and how the assignee can locate or understand the problem. Avoid overly dense or abstract language.
