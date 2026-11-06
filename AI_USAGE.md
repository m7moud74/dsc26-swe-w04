## Tools

Used an AI coding assistant (OpenCode/Beam) to draft the test suite and a reference implementation for local validation.

## What AI got wrong

The first draft used snake_case JSON keys and asserted only status codes, so it missed camelCase contract fields, problem media types, and exact problem types. It also initially omitted the reserve boundary case.

## In my own words

Pick one mutant your first draft of tests did not kill. Why not, and what did you add?

My first draft did not kill M01 (reserve boundary off by one) because it only checked clearly insufficient stock. I added a boundary case where `from_stock - quantity` exactly equals `reserve`, which the correct implementation allows but the `>` mutant rejects.

Why is a test that only asserts status_code == 409 weaker than one that asserts the problem type?

A 409 status code can come from different conflicts (below-reserve vs. not-pending). Asserting the problem type pins down which rule fired, so a mutant that changes the condition is actually caught.