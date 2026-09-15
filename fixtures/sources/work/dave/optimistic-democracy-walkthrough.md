# A walkthrough of Optimistic Democracy

Author wallet: 0x6c9de015919764af69580cbc7382a93cb788e36a
Published: 2026-10-05

This walkthrough follows one transaction through GenLayer's Optimistic
Democracy.

First the leader validator runs the contract and proposes a result. Then the
other validators run the same work themselves and vote on whether that result
is equivalent to their own under the contract's rule.

When the majority agrees, the result is accepted. During the appeal window
anyone can appeal, which asks a larger group of validators to evaluate it
again. After the window closes with no successful appeal, the result is final.
