# AI agent guidance

## Design (OOP)
* **Single responsibility** — A class or function should do one thing only.
* **Open / closed** — Open for extension, closed for modification.
* **Liskov substitution** — Subtypes must be replaceable for their base types.
* **Interface segregation** — Prefer small, focused interfaces over fat ones.
* **Dependency inversion** — Depend on abstractions, not concretions.
* **Composition over inheritance** — Favor assembling small behaviors over deep class hierarchies.

## Universal
* **DRY** — Every piece of knowledge should have a single source of truth.
* **KISS** — Simplicity is a feature; avoid unnecessary complexity.
* **YAGNI** — Don't build for hypothetical future needs.
* **Separation of concerns** — Keep distinct responsibilities in distinct modules.
* **Principle of least surprise** — Code should behave the way a reader would expect.
* **Law of Demeter** — A module should only talk to its immediate dependencies.

## Code Quality
* **Fail fast** — Surface errors early and loudly rather than letting them propagate silently.
* **Make it work → right → fast** — First get it running, then clean it up, then optimize if needed.
* **Boy scout rule** — Always leave code cleaner than you found it within scope.
* **Error handling is not optional** — Every external call, parse, or I/O operation must handle failure.
* **Log on failure** — When handling errors, record what failed and why, not only return or raise.
* **No placeholder code** — Never deliver `// TODO: implement this`. Implement it fully or state why it is not possible.
* **Explicit imports and dependencies** — Never assume something is available without importing it.

## Architecture
* **High cohesion, low coupling** — Things that belong together stay together; modules stay independent.
* **Design for testability** — If something is hard to test, it is poorly designed.
* **No premature optimization** — Profile before you optimize.
* **Version everything** — Code, config, infrastructure, data schemas.
* **Least privilege** — Grant only the access each component needs.
* **Secrets outside code** — Keep passwords and API keys in env or a vault, never in source or git.
* **Structured logging** — Log errors and important events with enough context to debug in production.
* **Metrics where it matters** — Track health and key flows (latency, errors) for services users depend on.
* **Validate and sanitize input** — Never trust client or user input — validate and sanitize at API and form boundaries.

## Mindset
* **Line length** — Maximum line length of 88 characters for Python source files (`.py`).
* **Code is read more than written** — Optimize for the reader, not the writer.
* **Explicit over implicit** — Clarity beats cleverness.
* **Embrace immutability** — Prefer data that does not change; it is easier to reason about.
* **Done means working, not elegant** — A task is done when the request is satisfied and nothing previously working is broken.

## Scope Control
* **Strict scope** — Do not add, remove, or refactor anything outside the explicit request.
* **Flag, don't fix** — If something broken is spotted nearby, note it, don't silently fix it.
* **Smallest viable change** — Prefer the minimal change that solves the problem.
* **One concern per response** — Don't bundle refactors with feature additions.
* **Preserve existing style** — Match conventions already in the file.
* **Cascade? Ask first** — If a change would cascade widely, stop and ask first.

## Communication
* **Clarify before assuming** — If intent is ambiguous, ask rather than guess.
* **Explain the why** — When suggesting something non-obvious, explain the reasoning.
* **Surface tradeoffs** — Name what is being traded away, not just what was chosen.
