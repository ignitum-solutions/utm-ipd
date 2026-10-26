# Universal Trust Model (UTM)

This guide describes the trust update and experimental assumptions implemented
in this repository. The research interface compares simulated behavior under
specified parameters; these experiments do not establish that the model predicts
human trust or performs uniformly across environments.

## Trust update implemented in this repository

The trust meter stores a value $T_t$ in $[0,1]$, initialized at $T_0=\theta$,
and a counter $n_t$, initialized at zero. Each observed event supplies a signed,
nonzero reward $R_t$. The experiments use severity $s_t=1$.

First update the counter:

$$
n_{t+1} = n_t + \mathbf{1}[R_t < T_t].
$$

Then select the learning rate:

$$
\alpha_t =
\begin{cases}
\alpha^+ & R_t > T_t, \\
\alpha^- & R_t \leq T_t.
\end{cases}
$$

Finally update and clip trust:

$$
T_{t+1} = \operatorname{clip}_{[0,1]}\left(
T_t + \alpha_t s_t (1+n_{t+1}\delta)(R_t-T_t)
\right).
$$

These equations correspond to `TrustMeter.observe()` in `utm/trust_meter.py`.
The counter records rewards below current trust; it is cumulative, not a count
of consecutive opponent defections. Its multiplier affects subsequent positive
and negative updates. A positive signed reward can still reduce trust if it is
below the current trust value.

For example, with $T=0.6$, $n=0$, and $\alpha^+=0.02$, reward $R=1$ gives
$T_{new}=0.608$. An adverse event increments the counter before computing the
update. Large adjustments can reach the clipping boundaries at 0 or 1.

## Parameters and decision rules

| Parameter | Meaning | Tournament / Moran default |
| --- | --- | --- |
| $\theta$ | Initial trust before the first interaction | 0.60 |
| $\alpha^+$ | Learning rate when reward exceeds current trust | 0.02 |
| $\alpha^-$ | Learning rate when reward is at or below current trust | 0.675 |
| $\delta$ | Cumulative update ramp after rewards below current trust | 0.45 |
| $\tau$ | Threshold used by the agent's decision rule | 0.50 |

The Trust Game uses separate initial defaults: $\theta=0.5$,
$\alpha^+=0.05$, $\alpha^-=0.5$, $\delta=0.55$, and $\tau=0.45$.
Each completed run records its actual parameters and seed.

The trust meter and action policy are separate. In the UTM-TFT variant, trust
below $\tau$ forces defection; otherwise the strategy uses its Tit-for-Tat
proposal. Other registered variants apply their own action rules using the
same trust meter. The hybrid switches permanently from TFT to WSLS when trust
is strictly greater than its promotion threshold, default 0.55; this can happen
on the first decision. Inner rules receive the actual played history, including
forced and noisy moves. In the Trust Game, trust below $\tau$ prevents investment.
A change in trust therefore need not change the action on every round.

## IPD rewards and tournament measurements

The mapping from moves to trust rewards is separate from the game payoffs used
to score a tournament:

| Agent move | Opponent move | Signed reward supplied to trust meter |
| --- | --- | --- |
| Cooperate | Cooperate | +1.0 |
| Defect | Cooperate | +0.5 |
| Defect | Defect | −0.2 |
| Cooperate | Defect | −1.0 |

A round-robin tournament measures payoff and cooperation against the selected
field, over the configured match length and repetitions. Use the payoff matrix
to identify opponent-specific differences. Use the score distribution to examine
variation across repetitions; it is not a confidence interval for every possible
opponent field.

A higher threshold can cause defection at trust values that would permit the
underlying strategy's proposal at a lower threshold. Whether that raises or
lowers payoff depends on the opponent and subsequent interactions. Higher
cooperation and higher payoff are separate measurements. Keep the opponent
field, noise, and match length fixed for a controlled parameter comparison,
then repeat across seeds and other fields to examine robustness.

## Moran process: persistence and fixation

The initial population is one UTM agent and $N-1$ cooperators, giving initial
UTM share $1/N$. Payoffs influence reproduction; random replacement introduces
variation. The process stops at fixation or the generation limit.

- Final share **0** means the UTM lineage was lost in this run.
- Final share **1** means the UTM lineage reached fixation.
- An intermediate final share means fixation was not observed within the
  generation budget. It does not establish long-term coexistence.

Higher payoff increases reproductive probability at a selection step, but does
not guarantee survival. A single seeded trajectory does not estimate fixation
probability. For that question, repeat independent seeds and report the number
of runs, population size, generation limit, and observed fixation frequency.
The mean share displayed in the interface is a mean along one trajectory.

## Investment / Trust Game: returns and threshold effects

When trust meets the threshold, the investor sends amount $a$. The partner
receives $3a$ and returns fraction $r$, producing net payoff $a(3r-1)$.
For $a>0$, fractions above one third produce profit and fractions below one
third produce loss. A seeded draw chooses the good or betrayal return fraction
on each round.

The current experiment supplies reward **+1 for nonnegative net payoff** and
**−1 for a loss**. No investment produces zero payoff and therefore a +1 trust
reward. Trust can recover while investment is suspended. This is an explicit
modeling assumption to consider when interpreting a trajectory.

Compare trust, cumulative payoff, investment fraction, and nonnegative-payoff
fraction together. Zero-payoff rounds are included in the last measurement;
it should not be described as a cooperation rate or treated as evidence of
profitable investment. The returned amount affects payoff magnitude, while the
trust update in this experiment uses only its sign.

## Reproducible comparisons and scope

Record the seed, parameter values, opponent field or population, repetitions,
software version, and any custom reward mapping. Use downloaded results and
settings to identify the configuration behind each observation. A seed allows
repetition within a fixed environment; it does not remove stochastic variation
across different seeds or establish general validity.

The meter stores numeric trust values, but clipping, the counter rule, and
threshold decisions make the full experiment more than a smooth scalar update.
Interpret results as outcomes of the implemented simulation and its assumptions.

## Citation

Carlisle (2025). *The Universal Trust Model.* See `CITATION.cff` and the repository
source for citation metadata and implementation details.
