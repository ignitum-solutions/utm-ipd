import type { RunKind } from './api';

export type ResearchPage = RunKind | 'sweeps' | 'guide';

/** Descriptions of the implemented experiments, not claims of model validity. */
export const RESEARCH: Record<ResearchPage, {
  title: string;
  question: string;
  design: string;
  measures: string;
  assumptions: string;
}> = {
  tournament: {
    title: 'Iterated Prisoner’s Dilemma tournament',
    question: 'How do UTM parameters affect payoff and cooperation against a selected set of strategies?',
    design: 'A round-robin tournament evaluates the selected strategies over repeated matches. Hold the opponent set and match length constant when comparing UTM parameters; vary seeds to examine stochastic variation.',
    measures: 'Mean score per turn, score variation across repetitions, cooperation rate, match wins, and pairwise payoffs.',
    assumptions: 'A higher threshold can suppress UTM cooperation when trust is below it. The payoff effect depends on the opponents: a strategy can obtain a high payoff while cooperating less. Compare payoff and cooperation separately. Rankings depend on the opponent field, noise, match length, and UTM settings; repeat across fields and seeds before generalizing.',
  },
  moran: {
    title: 'Moran evolutionary process',
    question: 'Can a single UTM agent persist or reach fixation in an initially cooperative population under payoff-based reproduction?',
    design: 'Start with one UTM agent and N−1 cooperators. Each generation selects an agent to reproduce in proportion to its payoff and replaces a randomly selected agent. Run until fixation or the selected generation limit.',
    measures: 'UTM population share by generation, final share, mean share over the observed trajectory, and the generation of fixation when reached.',
    assumptions: 'Higher payoff increases the probability of reproduction, but random replacement can still eliminate the UTM lineage. A final UTM share of 0 indicates loss; 1 indicates UTM fixation. An intermediate share at the generation limit is an unfinished trajectory, not evidence of a stable population. Repeat across seeds to estimate fixation frequency within the generation limit.',
  },
  trust: {
    title: 'Investment / Trust Game',
    question: 'How do return fractions and betrayal probability affect investment decisions, trust, and cumulative payoff?',
    design: 'The investor sends an amount only when trust meets the threshold. The amount is tripled, and the partner returns a configured fraction. A seeded random draw selects the good or betrayal return for each round.',
    measures: 'Trust after each round, cumulative net payoff, the fraction of rounds with an investment, and the fraction with a nonnegative payoff.',
    assumptions: 'For a positive investment, returning more than one third of the tripled amount gives a profit; less than one third gives a loss. This implementation supplies reward +1 for nonnegative payoff, including zero when no investment is made, and −1 for a loss. Trust can therefore recover during non-investment rounds. Compare investment fraction with payoff rather than interpreting zero-payoff rounds as cooperation.',
  },
  sweeps: {
    title: 'Parameter sweeps',
    question: 'How sensitive are tournament outcomes to changes in trust parameters or the signed IPD reward mapping?',
    design: 'Use the local tools for a parameter grid or random sample. Keep the comparison field fixed and retain the sampled parameters, seed, match length, repetitions, and software version.',
    measures: 'Scores for sampled settings, parameter rankings, and heatmaps of the selected comparison.',
    assumptions: 'A high-scoring sampled setting is conditional on the search space and opponent field. Repeat candidate settings across seeds and other fields before drawing a broader conclusion.',
  },
  guide: {
    title: 'Universal Trust Model',
    question: 'Definitions, update rules, and experimental assumptions used in this research interface.',
    design: '', measures: '', assumptions: '',
  },
};
