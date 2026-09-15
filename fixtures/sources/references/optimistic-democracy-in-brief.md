# Optimistic Democracy in brief

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

The equivalence principle tells validators when two results count as the same,
so honest nodes whose outputs differ only in wording can still agree.

Validators have stake at risk, which gives each of them a reason to evaluate
honestly rather than follow the leader.
