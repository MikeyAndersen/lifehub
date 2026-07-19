import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isNight } from '../src/components/paper/paperNight.js';

const todayAt = (hh, mm = 0) => {
  const d = new Date(); d.setHours(hh, mm, 0, 0);
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(hh)}:${p(mm)}:00`;
};
const weather = { sunrise: todayAt(4, 40), sunset: todayAt(21, 45) };
const clock = (hh, mm = 0) => { const d = new Date(); d.setHours(hh, mm, 0, 0); return d; };

test('dag mellem solopgang og solnedgang', () => {
  assert.equal(isNight(clock(12), weather), false);
  assert.equal(isNight(clock(21, 44), weather), false);
});

test('nat efter solnedgang og før solopgang', () => {
  assert.equal(isNight(clock(22), weather), true);
  assert.equal(isNight(clock(4, 0), weather), true);
});

test('fallback uden sol-tider: nat 22–06', () => {
  assert.equal(isNight(clock(23), null), true);
  assert.equal(isNight(clock(12), null), false);
});
