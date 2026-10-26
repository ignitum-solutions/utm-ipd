import { describe, expect, it } from 'vitest';
import { DEFAULT_CONFIG, csv, jsonHeaders, payload, readEvents } from './api';
import type { StreamEvent } from './api';

function bytes(chunks: Uint8Array[]) {
  return new ReadableStream<Uint8Array>({ start(controller) { for (const chunk of chunks) controller.enqueue(chunk); controller.close(); } });
}
describe('stream protocol', () => {
  it('decodes Unicode and multiple events split at every byte boundary', async () => {
    const data = new TextEncoder().encode('\n{"type":"progress","phase":"α⁺ learning","percent":20}\n{"type":"result","result":{"kind":"trust","config":{}}}\n');
    const events: StreamEvent[] = [];
    await readEvents(bytes([...data].map(value => new Uint8Array([value]))), event => events.push(event));
    expect(events.map(event => event.type)).toEqual(['progress', 'result']);
    expect(events[0].phase).toBe('α⁺ learning');
  });
  it('does not mistake a truncated stream for success', async () => {
    await expect(readEvents(bytes([new TextEncoder().encode('{"type":"started"}\n')]), () => {})).rejects.toThrow('before a result arrived');
  });
  it('surfaces streamed errors', async () => {
    await expect(readEvents(bytes([new TextEncoder().encode('{"type":"error","message":"Time limit reached"}\n')]), () => {})).rejects.toThrow('Time limit reached');
  });
  it('requires a terminal result payload', async () => {
    await expect(readEvents(bytes([new TextEncoder().encode('{"type":"result"}\n')]), () => {})).rejects.toThrow('result is missing');
  });
});
it('hashes exactly the POST bytes required by CloudFront OAC', async () => {
  expect((await jsonHeaders('abc'))['x-amz-content-sha256']).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'); // pragma: allowlist secret -- public SHA-256 "abc" test vector
});
it('sends only parameters relevant to the selected experiment', () => {
  expect(payload('moran', DEFAULT_CONFIG)).toHaveProperty('generations', 200);
  expect(payload('moran', DEFAULT_CONFIG)).not.toHaveProperty('opponents');
  expect(payload('trust', DEFAULT_CONFIG)).not.toHaveProperty('repetitions');
});
it('escapes CSV labels and prevents formula injection without altering numeric values', () => {
  expect(csv([{ Player: '=SUM(1,2)', Mean: -1 }])).toBe('"Player","Mean"\r\n"\'=SUM(1,2)","-1"');
  expect(csv([{ Player: 'A "quote"' }])).toContain('"A ""quote"""');
});
