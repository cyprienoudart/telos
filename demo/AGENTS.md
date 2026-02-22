# AGENTS.md — Cross-Iteration Knowledge Base

Accumulated learnings from the build process. The orchestrator appends to this file after each iteration. Subagents should read it before starting work.

## Conventions

<!-- Coding standards, naming conventions, patterns the project follows -->

## Gotchas

- Twenty CRM REST API returns 403 with Bearer token auth. Use **GraphQL** at `http://localhost:3000/graphql` instead — it works with the same token.
<!-- Things that went wrong and how they were fixed. Denial reasons from the reviewer. -->

## Patterns

<!-- Reusable patterns discovered during implementation (e.g., "all API routes use X middleware") -->

## Key Decisions

<!-- Architecture or design decisions made during implementation that future iterations should respect -->
