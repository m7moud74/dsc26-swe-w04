## Tools
AI coding assistant (OpenCode/Beam) used to draft tests and a local reference implementation.

## What AI got wrong
Initial draft used snake_case keys and only checked status codes, missing camelCase fields, problem media types, and exact problem types.

## In my own words
Pick one mutant your first draft of tests did not kill. Why not, and what did you add?
My first draft did not kill M01 (reserve boundary off by one) because it only checked clearly insufficient stock. I added a boundary case where from_stock minus quantity equals reserve, which the correct code allows but the mutant rejects.

Why is a test that only asserts status_code == 409 weaker than one that asserts the problem type?
A 409 can come from different conflicts. Asserting the problem type confirms which rule fired and catches mutants that swap conditions.