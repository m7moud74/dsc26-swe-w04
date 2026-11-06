## Tools

Used an AI coding assistant (OpenCode/Beam) to draft the test suite and reference implementation.

## What AI got wrong

Initial drafts used snake_case JSON keys and did not assert problem media types or exact problem types, so they would not kill the corresponding mutants.

## In my own words

Pick one mutant your first draft of tests did not kill. Why not, and what did you add?

My first draft did not kill M01 (reserve boundary off by one) because I only tested clearly below-reserve cases. I added a boundary case where from_stock - quantity exactly equals reserve, which should be allowed; an off-by-one mutant rejects it.

Why is a test that only asserts status_code == 409 weaker than one that asserts the problem type?

A status code alone does not distinguish which conflict occurred; asserting the problem type ensures the correct rule (below-reserve vs not-pending) triggered the error, preventing mutants that change the condition from passing silently.
