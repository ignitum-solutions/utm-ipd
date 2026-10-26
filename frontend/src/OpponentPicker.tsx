import { useMemo, useRef, useState } from 'react';
import { matchesOpponent, opponentLabel } from './opponents';

export default function OpponentPicker({ opponents, selected, onChange }: {
  opponents: string[];
  selected: string[];
  onChange: (names: string[]) => void;
}) {
  const [query, setQuery] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const sorted = useMemo(() => [...opponents].sort((a, b) => opponentLabel(a).localeCompare(opponentLabel(b), 'en', { sensitivity: 'base', numeric: true })), [opponents]);
  const visible = sorted.filter(name => matchesOpponent(name, query));
  const hiddenSelected = selected.filter(name => !visible.includes(name)).length;

  return <div className="opponent-picker">
    <div className="field-label">Classic opponents <span>{selected.length} selected</span></div>
    <label className="opponent-search-label" htmlFor="opponent-search">Filter opponents by name</label>
    <div className="opponent-search"><input ref={input} id="opponent-search" type="search" placeholder="Type a strategy name…" value={query} autoComplete="off" spellCheck={false} aria-describedby="opponent-filter-status" onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') e.preventDefault(); }} />{query && <button type="button" onClick={() => { setQuery(''); input.current?.focus(); }}>Clear filter</button>}</div>
    <p id="opponent-filter-status" className="opponent-filter-status" role="status">Showing {visible.length} of {opponents.length} opponents{hiddenSelected > 0 && query.trim() && ` · ${hiddenSelected} selected outside this filter`}</p>
    <div className="opponent-list" role="group" aria-label="Opponent options">{visible.length ? visible.map(name => <label key={name}><input type="checkbox" checked={selected.includes(name)} onChange={e => onChange(e.target.checked ? [...selected, name] : selected.filter(n => n !== name))} />{opponentLabel(name)}</label>) : <p className="opponent-no-matches">No opponents match “{query.trim()}”. Clear the filter or try another name.</p>}</div>
    <details className="opponent-name-note"><summary>About mathematical strategy names</summary><p>Golden ratio (φ), Pi (π), and Euler’s number (e) are built-in Axelrod strategies. They use these constants as targets for the combined cooperation-to-defection ratio. Their original identifiers are retained in saved settings and exports.</p></details>
  </div>;
}
