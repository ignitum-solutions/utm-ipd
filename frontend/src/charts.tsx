import type { Result } from './api';
import { opponentLabel } from './opponents';

function display(value: number) { return Number.isInteger(value) ? String(value) : value.toFixed(3); }

export function LineChart({ title, values, unit, firstStep = 0 }: { title: string; values: number[]; unit: string; firstStep?: number }) {
  if (!values.length) return null;
  const lo = Math.min(0, ...values), hi = Math.max(...values, 1), span = hi - lo || 1;
  const points = values.map((v, i) => `${44 + i / Math.max(values.length - 1, 1) * 530},${190 - (v - lo) / span * 160}`).join(' ');
  return <section className="chart"><h3>{title}</h3>
    <svg viewBox="0 0 600 235" role="img" aria-label={`${title}: ${values.length} values, from ${display(values[0])} to ${display(values.at(-1)!)}`}>
      {[0, .5, 1].map(t => <g key={t}><line className="grid-line" x1="44" x2="574" y1={190 - t * 160} y2={190 - t * 160} /><text x="36" y={194 - t * 160} textAnchor="end">{display(lo + t * span)}</text></g>)}
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinejoin="round" />
      <text x="44" y="215">{firstStep}</text><text x="574" y="215" textAnchor="end">{values.length - 1 + firstStep} {unit}</text>
    </svg>
  </section>;
}

function quantile(values: number[], q: number) {
  const sorted = [...values].sort((a, b) => a - b), position = (sorted.length - 1) * q;
  const low = Math.floor(position), fraction = position - low;
  return sorted[low] + fraction * ((sorted[low + 1] ?? sorted[low]) - sorted[low]);
}

export function TournamentCharts({ result }: { result: Result }) {
  const rows = result.leaderboard ?? [], players = (result.players ?? []).map(opponentLabel), scores = result.scores ?? [];
  const payoff = result.payoff_matrix ?? [];
  const maxScore = Math.max(5, ...scores.flat());
  const scale = (value: number) => 220 + value / maxScore * 340;
  return <>
    <div className="chart-grid"><section className="chart"><h3>Mean score per turn</h3><p className="muted">Mean per-turn payoff across other players and repetitions. Self-play is excluded.</p>
      {rows.map((row, i) => <div className="bar-row" key={i}><span title={opponentLabel(String(row.Player))}>{opponentLabel(String(row.Player))}</span><div className="bar-track"><div style={{ width: `${Number(row.Mean) / maxScore * 100}%` }} /></div><strong>{Number(row.Mean).toFixed(2)}</strong></div>)}
    </section><section className="chart"><h3>Matches won</h3><p className="muted">Total wins across repetitions; ties are excluded.</p>
      {players.map((name, i) => { const wins = (result.wins?.[i] ?? []).reduce((a, b) => a + b, 0); return <div className="bar-row" key={i}><span title={name}>{name}</span><strong>{wins}</strong></div>; })}
    </section></div>
    <section className="chart"><h3>Score distribution</h3><p className="muted">Minimum, first quartile, median, third quartile, and maximum across repetitions.</p>
      <svg className="distribution" viewBox={`0 0 600 ${players.length * 30 + 35}`} role="img" aria-label="Score distributions by strategy">
        {players.map((name, i) => { const values = scores[i]; if (!values?.length) return null; const y = i * 30 + 20; const q = [0, .25, .5, .75, 1].map(p => scale(quantile(values, p))); return <g key={i}><text x="5" y={y + 4}>{name.length > 29 ? name.slice(0, 28) + '…' : name}</text><line x1={q[0]} x2={q[4]} y1={y} y2={y} stroke="var(--accent)" /><rect x={q[1]} y={y - 8} width={Math.max(1, q[3] - q[1])} height="16" fill="var(--accent-soft)" stroke="var(--accent)" /><line x1={q[2]} x2={q[2]} y1={y - 8} y2={y + 8} stroke="var(--accent)" /></g>; })}
      </svg>
    </section>
    <section className="chart"><h3>Payoff matrix</h3><p className="muted">Average score per turn for the row strategy against the column strategy. Diagonal entries are self-play; leaderboard aggregates exclude self-play.</p><div className="table-scroll"><table><thead><tr><th>Strategy</th>{players.map((_, i) => <th key={i} title={players[i]}>{i + 1}</th>)}</tr></thead><tbody>{players.map((name, i) => <tr key={i}><th>{i + 1}. {name}</th>{payoff[i]?.map((v, j) => <td key={j} style={{ background: `rgba(237, 128, 74, ${Math.max(0, Math.min(.3, v / 5 * .3))})` }}>{v.toFixed(2)}</td>)}</tr>)}</tbody></table></div></section>
  </>;
}
