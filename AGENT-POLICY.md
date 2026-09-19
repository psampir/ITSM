# AGENT-POLICY.md

Blast-radius policy for the sub-agents in `.claude/agents/` (Stretch S2). Each denial names a tool the
`reviewer` sub-agent may never use, and why. The reviewer's job is to read and comment, so every capability
that could change the machine, publish to the remote, or pull untrusted instructions from the network is denied
at the tool level rather than left to its judgement.

- Bash(rm *): the reviewer only reads and comments; deleting files is the author's decision, not the reviewer's, and an accidental delete is unrecoverable without a snapshot.
- Bash(git push *): pushing publishes to the public remote and is the author's act of submission; a reviewer must never publish a revision the author has not chosen.
- Bash(docker *): the reviewer inspects the compose files and sources as text; building or running containers is outside its read-only blast radius and can consume disk and network.
- WebFetch: the reviewer works only from the local repository; fetching external content would let a remote page inject instructions into the review, which is exactly the risk a narrow denylist exists to remove.
