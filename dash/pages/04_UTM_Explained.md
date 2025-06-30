# Universal Trust Model (UTM)

The UTM is a lightweight, continuous **trust meter** that rises when an
interaction is favourable and falls when it is harmful.  
Because it is **domain-agnostic**, the same scalar can drive any downstream
policy—whether in IPD, public-goods games, or a larger cognitive agent.

---

## 1 How the trust meter updates

### Quick one-liner for non-specialists

$$
\boxed{T_{\text{new}} = T_{\text{old}} + \alpha \,(R - T_{\text{old}})}
$$

Think of it as **“old trust” plus a learning-rate times the surprise of the
result.”**

- If the result $$R$$ is **better** than expected, trust goes **up**.
- If the result is **worse**, trust goes **down**.

---

### Quick intuition for UTM

- Trust lies between **0 = none** and **1 = full**.
- It starts at **θ**.
- A _good_ outcome nudges trust **up** by **α⁺**.
- A _bad_ outcome drops trust **down** by **α⁻ × (1+δ)**.
- Trust is clamped to $$[0,1]$$.
- If trust sinks below **τ**, the agent defects until trust recovers above τ.

---

### UTM asymmetric update (spreadsheet one-liner)

$$
T_{t+1}= \operatorname{clip}\!\Bigl(
T_t + \alpha^{+}\,\text{coop} - \alpha^{-}(1+\delta)\,\text{defect},
\,0,\,1\Bigr)
$$

`coop = 1` for cooperation `defect = 1` for betrayal.

---

### Full equation

<details>
<summary>Show LaTeX derivation</summary>

Let

- $$T_t \in [0,1]$$ be the current trust level
- $$o_t \in \{+1,-1\}$$ be the signed outcome (+1 = cooperate, –1 = betray).

$$
T_{t+1} =
\operatorname{clip}\!\bigl(
  T_t +
  \alpha^{+}\,\mathbf 1_{\\{o_t=+1\\}} -
  \alpha^{-}(1+\delta)\,\mathbf 1_{\\{o_t=-1\\}},
  0,\;1
\bigr)
$$

</details>

---

### Parameter glossary

| Symbol | Range   | Meaning                                                   | Demo default |
| ------ | ------- | --------------------------------------------------------- | ------------ |
| θ      | 0 – 1   | Initial trust                                             | 0.60         |
| α⁺     | 0 – 0.5 | Positive learning-rate                                    | 0.02         |
| α⁻     | 0 – 1   | Negative learning-rate                                    | 0.68         |
| δ      | 0 – 1   | Extra penalty for betrayal                                | 0.45         |
| τ      | 0 – 1   | Defection threshold (IPD Related Variable - UTM-TFT only) | 0.50         |

_Internal research explores more nuanced α-schedules; those variants are
withheld pending IP filings._

---

## 2 Decision rule in **UTM-TFT**

1. Baseline action comes from classic Tit-for-Tat.
2. If current trust $$T_t < τ$$ the baseline move is overridden with **Defect**
   until trust recovers.

This blends TFT reciprocity with an organism-like “loss of faith” when trust
drops too low.

---

## 3 Why the model matters

- **Continuous & differentiable** – can feed directly into ML / RL agents.
- **Parametric** – covers cautious, forgiving, or punitive personalities via five knobs.
- **Tiny** – $$O(1)$$ memory and compute.

The playground demonstrates:

- Stable cooperation with friendly partners.
- Tunable sensitivity to betrayal (change sliders).
- Robustness checks under the _Noise %_ control.

For graded-severity games (e.g., Investment / Trust Game) replace the
binary outcome with a signed, scaled reward; the same rule applies.

---

## Citation (draft)

> Carlisle (2025). _The Universal Trust Model._ Working paper.  
> Git URL:`https://github.com/ignitum-solutions/utm-ipd`
