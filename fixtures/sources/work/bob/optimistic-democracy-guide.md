# My guide to Optimistic Democracy

Author wallet: 0x41c1be19a7726e593e09f2e8748369afbeba2580
Published: 2026-09-12

GenLayer settles transactions that need judgment with a process called
Optimistic Democracy.

A leader validator proposes a result for the transaction. A set of other
validators then repeat the same work independently and vote on whether the
leader's result is acceptable under the contract's equivalence rule.

If a majority agrees, the result is accepted optimistically. It becomes final
once an appeal window passes without a successful challenge.

Anyone who disagrees with an accepted result can appeal during that window. An
appeal brings in a larger group of validators, who evaluate the transaction
again.
