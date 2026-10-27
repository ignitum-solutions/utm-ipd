# Universal Trust Model (UTM)

This repository evaluates a parameterized trust-update mechanism and its decision
policies in the Iterated Prisoner's Dilemma (IPD), a game in which two players
repeatedly choose whether to cooperate or defect. Tournament results measure
payoff and cooperation against a specified field of opponents. The Trust Game,
Moran process, and local parameter sweeps provide additional exploratory
experiments and stress tests of particular assumptions.

These simulations do not establish prediction of human trust, general
superiority, or universality across domains. They also do not establish
trust-risk separation: distinguishing beliefs about a partner from the risk
associated with the available actions. “Universal Trust Model” is the project
and model name, rather than an empirical conclusion established here.

## What the IPD experiment separates

Four parts of the experiment have different roles:

1. **Trust meter.** A numeric state $T$ summarizes mapped outcomes for one
   counterpart. It lies in $[0,1]$, but is not automatically a calibrated
   probability of cooperation, a percentage accuracy, or an observed human belief.
2. **Outcome-to-reward mapping.** Played moves are converted to a signed reward
   $R$ that supplies the target for the trust update. This encoding is a modeling
   choice; its values are listed with the game payoffs below.
3. **Action policy.** A strategy uses trust and, for delegated policies, played
   history to choose the next move. The cooperation threshold $\tau$ belongs to
   this decision rule, not to the trust update itself.
4. **External game payoff.** The same Prisoner's Dilemma payoff matrix scores
   every player. Internal trust rewards do not replace these scoring payoffs.

## Rescorla-Wagner and delta learning

[Rescorla and Wagner (1972)](https://www.columbia.edu/~rk566/Session4/Theory%20of%20Pavlovian%20Conditioning.pdf)
proposed a model of Pavlovian conditioning: learning about outcomes from
predictive stimuli, or cues. Each cue has an associative strength, a value
representing its learned relationship with the outcome. The update depends on
prediction error, the difference between an encoded outcome and its prediction.
This prediction-error structure is also present in UTM.

For a restricted comparison, consider a single-cue learner with current value
$V_t$, encoded outcome $\lambda_t$, and fixed update strength $k$. Its delta
rule moves the current value toward the outcome:

$$
V_{t+1} = V_t + k(\lambda_t - V_t).
$$

UTM also adjusts a current value toward an encoded outcome. It uses a variable
update strength $k_t$ and clips the result to $[0,1]$, replacing values outside
that interval with its nearest boundary:

$$
T_{t+1} = \operatorname{clip}_{[0,1]}\left(T_t + k_t(R_t-T_t)\right).
$$

The effective update strength, or gain, combines a conditional learning rate
$\alpha_t$, event severity $s_t$, and a history-dependent multiplier. Here $n_{t+1}$ is the
counter after including the current event, and $\delta$ controls its contribution:

$$
k_t = \alpha_t s_t(1+n_{t+1}\delta).
$$

| Quantity | Single-cue fixed-rate learner | Implemented UTM |
| --- | --- | --- |
| Current value | $V_t$ | $T_t$ |
| Target outcome | $\lambda_t$ | Signed reward $R_t$ |
| Prediction error | $\lambda_t-V_t$ | $R_t-T_t$ |
| Update strength | Fixed $k$ | History-dependent $k_t$ |

With $\alpha^+=\alpha^-=k$, $\delta=0$, severity $s_t=1$, matched initialization,
and the same outcome encoding, the recurrences agree wherever clipping is
inactive. Changing variable names or their interpretation does not change that
mathematical equivalence.

The full Rescorla-Wagner model allows multiple cues to contribute to a common
prediction; their summed associative strengths enter the prediction error.
UTM's single trust state does not implement this complete multi-cue model.
The 1972 formulation permits learning parameters to depend on the cue and
outcome. Rescorla-Wagner associative strengths are not universally clipped to
$[0,1]$, and the fixed-rate comparison above does not represent every variant
of that learning rule.

Relative to this specified comparator, UTM uses conditional learning rates,
a cumulative below-current-trust counter, explicit clipping, a domain-specific
reward mapping, and separate IPD policies. These choices do not establish
historical novelty; asymmetric learning, initial values, and bounded scores
should not be regarded as unique to UTM. No experiment here demonstrates that
UTM resolves documented limitations of Rescorla-Wagner learning. A learning
rule alone is also not an IPD opponent. A tournament comparison needs a stated
action policy and comparable information about played moves.

## Event timing and memory

The meter starts at $T_0=\theta$ with counter $n_0=0$. Each observation supplies
a finite, nonzero signed reward. To count events whose reward falls below current
trust, the implementation first updates the counter:

$$
n_{t+1} = n_t + \mathbf{1}[R_t < T_t].
$$

The indicator $\mathbf{1}$ is 1 when the condition is true and 0 otherwise.
The current event therefore contributes to its own multiplier. The counter is
cumulative, rather than a count of consecutive defections. A later reward above
current trust does not clear it. Its multiplier affects both positive and negative
updates. A positive reward can reduce trust when it is below the current value.

To choose the learning rate, the code compares the reward with current trust:

$$
\alpha_t =
\begin{cases}
\alpha^+ & R_t > T_t, \\
\alpha^- & R_t \leq T_t.
\end{cases}
$$

Equality selects $\alpha^-$ but leaves trust unchanged because prediction error
is zero; it does not increment the counter. The experiments currently use
severity $s_t=1$. The meter has no elapsed-time decay: state changes through
observations or an explicit reset.

The accumulated gain can exceed 1, so an update can overshoot its target and
reach a clipping boundary. Clipping, the counter's discrete increment, and
threshold-based decisions mean the overall system is not globally smooth or
differentiable.

### Worked examples of the core mechanism

For $T=0.6$, $n=0$, $\alpha^+=0.02$, and severity 1, observing reward 1 gives
$T_{\mathrm{next}}=0.6+0.02(1-0.6)=0.608$. The counter remains zero.

Equal current trust need not imply equal subsequent updates. Set $\theta=0.5$,
$\alpha^+=0.05$, $\alpha^-=0.5$, and $\delta=0.3$, with severity 1 throughout.
One meter receives no observations. Another receives the graded rewards
$[0.49,0.5935]$: its trust first falls to 0.4935, then returns to 0.5.
The next reward 1 distinguishes them:

| Prior observations | Trust before reward 1 | Counter | Trust after reward 1 |
| --- | --- | --- | --- |
| None | 0.5 | 0 | 0.525 |
| 0.49, then 0.5935 | 0.5 | 1 | 0.5325 |

This is a core-mechanism calculation using graded rewards, not an IPD
performance result. The default IPD reward mapping does not use those two
intermediate rewards.

## IPD policies and initial settings

A UTM strategy updates trust from the previous played round when making its
next decision. The registered policies then use that state as follows:

- **Trust-only IPD:** cooperate when $T\geq\tau$; otherwise defect.
- **UTM-TFT:** below $\tau$, defect. Otherwise use Tit-for-Tat, which starts with
  cooperation and then copies the opponent's previous played move.
- **UTM-WSLS:** below $\tau$, defect. Otherwise use Axelrod's Win-Stay-Lose-Shift
  rule, which starts with cooperation, proposes cooperation after CC or DD,
  and proposes defection after CD or DC. The first letter is the agent's move.
- **TFT-to-WSLS hybrid:** begin with TFT and switch permanently within the match
  to WSLS when trust is strictly greater than the promotion threshold, whose
  default is 0.55. The separate cooperation threshold still gates either rule.
  Promotion can occur on the first decision if initial trust already exceeds
  0.55; it does not require a history of conflict.

Delegated policies receive actual played histories, including moves forced by
the trust gate or flipped by noise. On promotion, the hybrid's new WSLS rule
receives the history already played. Resetting a strategy clears played histories
and the counter, restores initial trust, and returns the hybrid to TFT. A fresh match
therefore starts from its configured initial state, even if it immediately
promotes again.

These are the web interface's initial tournament and Moran settings, which can
differ from the defaults of individual Python strategy constructors:

| Parameter | Meaning | Web IPD / Moran setting |
| --- | --- | --- |
| $\theta$ | Initial trust | 0.60 |
| $\alpha^+$ | Rate when reward exceeds current trust | 0.02 |
| $\alpha^-$ | Rate when reward is at or below current trust | 0.675 |
| $\delta$ | Cumulative update multiplier coefficient | 0.45 |
| $\tau$ | Cooperation threshold | 0.50 |

Defaults and named presets are illustrative parameter configurations. Their
names do not identify measured human personality types or establish optimal
settings. Record the resolved values for each experiment.

## IPD rewards and tournament results

For the hosted IPD experiment, the internal trust rewards and external game
payoffs are:

| Moves (agent, opponent) | Signed trust reward | Game payoffs (agent, opponent) |
| --- | --- | --- |
| C, C | +1.0 | 3, 3 |
| D, C | +0.5 | 5, 0 |
| D, D | −0.2 | 1, 1 |
| C, D | −1.0 | 0, 5 |

These reward values are assumptions about how outcomes affect trust. In
particular, an agent's own defection against a cooperator supplies reward +0.5;
the mapping is not solely a description of the opponent's action. Local research
tools allow explicit nonzero reward mappings without changing scoring payoffs.

A round-robin tournament measures payoff and cooperation over the selected
match length, repetitions, opponent field, and noise level. Leaderboard means
use per-turn payoffs against non-self player slots, averaged across repetitions.
Self-play appears in the payoff matrix but is excluded from leaderboard
aggregates. Equal exact means share a rank, and cooperation rates use recorded
non-self cooperation counts divided by recorded non-self turns.

Use the payoff matrix to examine particular opponents and the score distribution
to inspect variation across repetitions. That distribution is not a confidence
interval for every possible opponent field. A higher cooperation threshold can
suppress cooperation; its payoff effect depends on subsequent interactions.
Keep the comparison field and protocol fixed when changing a parameter, then
repeat across seeds and fields before generalizing. Losses and low cooperation
are possible outcomes of these policies.

## Additional exploratory experiments

These experiments probe assumptions and possible failure modes beyond the
primary IPD tournament. They can expose an implementation problem or a limitation
of a specified hypothesis. Passing a stress test does not prove universality,
and a limitation of one outcome mapping or action policy does not automatically
refute every version of the underlying model.

### Investment / Trust Game

When trust meets the investment threshold, the investor sends amount $a$. The
partner receives $3a$ and returns fraction $r$, so net payoff is $a(3r-1)$.
For $a>0$, a return fraction above one third produces profit and a fraction below
one third produces loss. A seeded draw selects the good or betrayal return
fraction each round. Initial settings are $\theta=0.5$, $\alpha^+=0.05$,
$\alpha^-=0.5$, $\delta=0.55$, and $\tau=0.45$.

The current adapter supplies reward **+1 for nonnegative net payoff** and
**−1 for a loss**. No investment gives zero payoff and therefore a +1 trust
reward. This permits recovery without fresh partner evidence. The amount
returned affects payoff magnitude. The trust reward uses only the distinction
between nonnegative and negative payoff.

Compare trust, cumulative payoff, investment fraction, and nonnegative-payoff
fraction separately. Zero-payoff inactivity is included in the last measure;
it is not cooperation or evidence of profitable investment. Reward zero is
currently rejected by the meter. Severity zero is not a missing-observation
operation either: a below-trust reward can still increment the counter even
though it leaves trust unchanged.

### Moran process

The initial population contains one UTM agent and $N-1$ cooperators, giving an
initial UTM share of $1/N$. Axelrod's birth-death process selects reproduction
in proportion to payoff and replaces a randomly selected agent. The simulation
stops at fixation, when one type occupies the whole population, or at the
requested generation limit.

With the default UTM-TFT policy and noiseless cooperative play, the UTM agent
can act like the resident Cooperators. Equal payoffs remove a payoff advantage;
population composition can then change through neutral drift, the random
effect of reproduction and replacement.

Final share 0 means the UTM lineage was lost; final share 1 means UTM fixation.
An intermediate final share means fixation was not observed within the budget,
without establishing long-term coexistence. Higher payoff can increase
reproductive probability but cannot guarantee survival under random replacement.
A single seeded trajectory does not estimate fixation probability. Repeat
independent seeds and report population size, generation limit, run count, and
observed fixation frequency. The displayed mean share averages one trajectory.

### Local parameter sweeps

Sweeps sample parameter settings or signed reward mappings against a chosen
opponent field. The local heatmap displays the mean of sampled observations
in each cell. A high-scoring sample is conditional on the search space and
protocol; it is not an established optimum or evidence of general superiority.
Retain sampled parameters and adverse outcomes, and repeat candidates across
seeds and other opponent fields.

## Evidence and reproducibility

The repository's tests check specified arithmetic, match resets, delegated
histories, disabled-gate agreement with classic strategies, and known payoff
and cooperation counts. A control also retains a known UTM loss. These are
software and mechanism checks, rather than empirical validation of human trust.

Record seeds, effective parameters, player order, opponent field or population,
repetitions, noise, software versions, and any custom reward mapping. Downloaded
results include the scoring protocol and implementation identifiers. Repeating
a seed within a fixed environment does not remove variation across seeds.

Comparisons with held-out behavioral data, parameter recovery, and broader
comparisons of fitted behavioral models remain future work here. Held-out data
are observations reserved from model fitting to assess prediction. Parameter
recovery asks whether a fitting procedure can recover known parameters from
simulated data. [Wilson and Collins (2019)](https://doi.org/10.7554/eLife.49547)
describe these checks and model validation; none is supplied by a favorable
simulation ranking alone.

## References

- Rescorla, R. A., and Wagner, A. R. (1972). A theory of Pavlovian conditioning:
  Variations in the effectiveness of reinforcement and nonreinforcement. In
  *Classical Conditioning II: Current Research and Theory*, pp. 64–99.
  [Chapter PDF](https://www.columbia.edu/~rk566/Session4/Theory%20of%20Pavlovian%20Conditioning.pdf).
- Wilson, R. C., and Collins, A. G. E. (2019). Ten simple rules for the
  computational modeling of behavioral data. *eLife*, 8:e49547.
  [Article](https://doi.org/10.7554/eLife.49547).
- Carlisle (2025). *The Universal Trust Model*. See
  [repository citation metadata](https://github.com/ignitum-solutions/utm-ipd/blob/main/CITATION.cff)
  and the source code for the implementation described here.
