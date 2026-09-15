# How GenLayer decides when there is no single right answer

Author wallet: 0xef6e006cd8a68c9cfe88a3640415ab0c79c71921
Published: 2026-09-14

This guide explains how GenLayer's Optimistic Democracy reaches agreement on
results that need judgment, such as reading a web page or weighing evidence.

## One proposes, the others check

For each such transaction one validator acts as the leader and proposes a
result. The other validators repeat the work on their own, with their own
models and their own web requests, and then vote on whether the leader's
result is acceptable.

Think of it like a group project where one person drafts the answer and the
rest of the group redo the working before they sign it.

## What counts as the same answer

Two models rarely write identical sentences. The contract therefore states an
equivalence rule: the fields that decide what happens must match, while
wording and explanation may differ. A validator votes yes when its own result
and the leader's are equivalent under that rule.

## Accepted is not yet final

A result that wins a majority is accepted, but anyone who thinks the accepted
result is wrong can appeal before the appeal window closes. An appeal sends
the transaction to a larger group of validators, and only when the window
passes without a successful appeal does the result become final.

## Why the material is treated as data

Everything a validator reads is evidence, not instruction. A submitted page
might even contain a line such as "ignore your previous instructions", and a
well-built contract tells its validators to read that as text on the page,
never as a command.

## Why validators bother to be honest

Validators put stake at risk. Agreeing with a leader they did not check
exposes them to the same penalty as the leader when a larger appeal round
overturns the result, so checking is the safer strategy.
