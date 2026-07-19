import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  stripEmoji, classBadge, postBadge, partitionInbox, primaryAction,
  quietAction, dueLine, pickHighlights, nextDays,
} from '../src/components/paper/paperLogic.js';

const at = (off, hh, mm = 0) => {
  const d = new Date();
  d.setDate(d.getDate() + off); d.setHours(hh, mm, 0, 0);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(hh)}:${p(mm)}:00`;
};

test('stripEmoji fjerner emoji men bevarer dansk tekst', () => {
  assert.equal(stripEmoji('Fødselsdagsgave 🎁'), 'Fødselsdagsgave');
  assert.equal(stripEmoji('Æg og mælk'), 'Æg og mælk');
});

test('stripEmoji fjerner flag, hudtone-modifikatorer og ZWJ-sekvenser', () => {
  assert.equal(stripEmoji('Flag 🇩🇰 dag'), 'Flag dag');
  assert.equal(stripEmoji('Godt 👍🏽 klaret'), 'Godt klaret');
  assert.equal(stripEmoji('Familie 👨‍👩‍👧‍👦 tur'), 'Familie tur');
});

test('classBadge finder klassebetegnelser', () => {
  assert.equal(classBadge('Skovtur 2.B mandag'), '2.B');
  assert.equal(classBadge('SFO lukker kl. 15'), 'SFO');
  assert.equal(classBadge('Ugens bogstav er S'), null);
});

test('classBadge finder ÆØÅ-klasser uanset position (JS \\b er ASCII-only)', () => {
  assert.equal(classBadge('2.Ø tur i morgen'), '2.Ø');
  assert.equal(classBadge('Skovtur 2.Ø mandag'), '2.Ø');
  assert.equal(classBadge('Idræt i dag for 2.Ø'), '2.Ø');
  assert.equal(classBadge('Fødselsdag i 2.Æ på fredag'), '2.Æ');
  assert.equal(classBadge('Forældremøde for 2.Å'), '2.Å');
});

test('postBadge mapper sender_kind og tone', () => {
  assert.deepEqual(postBadge({ sender_kind: 'bank', importance: 'high' }),
                   { label: 'BANK', tone: 'accent' });
  assert.deepEqual(postBadge({ sender_kind: 'nyhedsbrev', importance: 'low' }),
                   { label: 'LAV PRIORITET', tone: 'neutral' });
  assert.deepEqual(postBadge({ sender_kind: 'andet', importance: 'normal' }),
                   { label: 'INFO', tone: 'neutral' });
});

test('partitionInbox deler pending i handlinger og nyhedsbreve', () => {
  const post = {
    info: [
      { id: 1, status: 'pending', sender_kind: 'nyhedsbrev', title: 'Ugens tilbud' },
      { id: 2, status: 'pending', sender_kind: 'kommune', title: 'Årsopgørelse' },
      { id: 3, status: 'briefed', sender_kind: 'kommune', title: 'Gammel' },
    ],
    recent: [
      { id: 4, status: 'pending', intent: 'handling', sender_kind: 'forsikring', title: 'Forny' },
      { id: 5, status: 'approved', intent: 'handling', sender_kind: 'bank', title: 'Betalt' },
    ],
  };
  const { actionable, newsletters } = partitionInbox(post);
  assert.deepEqual(actionable.map((i) => i.id), [4, 2]);
  assert.deepEqual(newsletters.map((i) => i.id), [1]);
});

test('primary/quiet action afhænger af intent', () => {
  const handling = { intent: 'handling', title: 'Betal elregning' };
  const info = { sender_kind: 'kommune', title: 'Ny info' };
  assert.deepEqual(primaryAction(handling), { label: 'Opret opgave: Betal elregning', action: 'approve' });
  assert.deepEqual(quietAction(handling), { label: 'Arkivér', action: 'archive' });
  assert.deepEqual(primaryAction(info), { label: 'Læs & kvittér', action: 'archive' });
  assert.deepEqual(quietAction(info), { label: 'Senere', action: 'defer' });
});

test('primaryAction fjerner emoji fra titlen i handlings-labelen', () => {
  const handling = { intent: 'handling', title: 'Betal elregning 💸' };
  assert.deepEqual(primaryAction(handling),
    { label: 'Opret opgave: Betal elregning', action: 'approve' });
});

test('dueLine på dansk', () => {
  const now = new Date();
  assert.equal(dueLine(at(0, 14), now), 'i dag inden 14:00');
  assert.equal(dueLine(at(1, 17), now), 'i morgen');
  assert.equal(dueLine(at(-1, 12), now), 'forfalden');
  assert.equal(dueLine(null, now), null);
});

test('dueLine bruger injiceret now, ikke det rigtige ur (deterministisk)', () => {
  // Fjernt fra det virkelige ur med vilje, så testen ikke tilfældigt består
  // pga. sammenfald med den faktiske systemdato.
  const now = new Date('2030-01-15T10:00:00');
  const twoDaysAgo = '2030-01-13T09:00:00';
  assert.equal(dueLine(twoDaysAgo, now), 'forfalden');
});

test('pickHighlights: kommende event i dag først, maks 2', () => {
  const now = new Date(); now.setHours(10, 0, 0, 0);
  const doc = {
    events: [{ title: 'Svømning — Alma', start: at(0, 16), all_day: false }],
    tasks: [{ id: 1, title: 'Køb gave', due: at(0, 14) }],
    aula: { recent: [] },
  };
  const hl = pickHighlights(doc, now);
  assert.equal(hl.length, 2);
  assert.match(hl[0].text, /Svømning — Alma kl\. 16:00/);
  assert.equal(hl[0].urgent, true);
});

test('pickHighlights bruger injiceret now til at afgøre forfalden opgave', () => {
  // Fjernt fra det virkelige ur med vilje, så testen ikke tilfældigt består
  // pga. sammenfald med den faktiske systemdato.
  const now = new Date('2030-01-15T10:00:00');
  const doc = {
    events: [],
    tasks: [{ id: 1, title: 'Aflever tilladelse', due: '2030-01-13T09:00:00' }],
    aula: { recent: [] },
  };
  const hl = pickHighlights(doc, now);
  assert.equal(hl.length, 1);
  assert.equal(hl[0].text, 'Aflever tilladelse');
  assert.equal(hl[0].urgent, true);
});

test('nextDays grupperer 3 kommende dage', () => {
  const now = new Date();
  const days = nextDays([
    { title: 'Tandlæge', start: at(1, 9), all_day: false },
    { title: 'Cykeltur', start: at(2, 10), all_day: false },
  ], now, 3);
  assert.equal(days.length, 3);
  assert.deepEqual(days[0].badges, ['Tandlæge']);
  assert.deepEqual(days[2].badges, []);
});
