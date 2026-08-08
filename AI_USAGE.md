# AI usage

I directed this build phase by phase from a written plan, reviewed every diff,
and made every commit myself. The agent was configured never to run git — that
is why the history is granular rather than a handful of large drops.

Claude Code produced project scaffolding, the Dockerfiles, the Compose stack,
the GitHub Actions workflows, the Grafana dashboard JSON, the Terraform, and
drafts of the documentation.

I ran every acceptance check personally: the schema verification against
Postgres, the API transcript, the two clean-stack startups, the PR pipeline, the
failure drill and its alert timings, the backup/restore/verify test including
the negative case, and the AWS deployment.

Examples of corrections I made to generated work: the initial migration had been
verified against a throwaway database rather than the real one; a reported
"env.py bug" was actually my own exported shell variables overriding `.env`; a
"read/write" edge in the architecture diagram pointed at the wrong component;
Redis had been placed outside the data tier; and the Grafana password silently
defaulted to "admin" through a Compose fallback, which I caught while writing
the configuration table and fixed.

`ENGINEERING_DECISIONS.md` was written by me. No public template or tutorial
repository was adapted.
