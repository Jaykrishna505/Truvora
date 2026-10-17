const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function load(fetch) {
  const element = { addEventListener() {} };
  let onTimeout;
  let cleared = false;
  const context = vm.createContext({
    document: { querySelector: () => element, querySelectorAll: () => [] },
    fetch, AbortController,
    setTimeout(callback) { onTimeout = callback; return 1; },
    clearTimeout() { cleared = true; },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/auth.js'), 'utf8'), context);
  return { api: context.api, timeout: () => onTimeout(), cleared: () => cleared };
}

test('network errors become a visible error result', async () => {
  const client = load(async () => { throw new TypeError('Failed to fetch'); });
  assert.match((await client.api('/api/auth/register')).error, /Could not connect/);
  assert.equal(client.cleared(), true);
});

test('HTML server errors do not leave the form pending', async () => {
  const client = load(async () => ({
    ok: false, status: 500, json: async () => { throw new SyntaxError('HTML'); },
  }));
  assert.match((await client.api('/api/auth/register')).error, /HTTP 500/);
});

test('validation errors retain their message', async () => {
  const client = load(async () => ({
    ok: false, status: 409, json: async () => ({ detail: 'Account already exists.' }),
  }));
  assert.equal((await client.api('/api/auth/register')).error, 'Account already exists.');
});

test('valid success remains successful', async () => {
  const client = load(async () => ({ ok: true, json: async () => ({ ok: true }) }));
  assert.equal((await client.api('/api/auth/register')).ok, true);
});

test('timeout cancels fetch and advises checking login before retrying', async () => {
  const client = load((url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const result = client.api('/api/auth/register');
  client.timeout();
  assert.match((await result).error, /timed out.*log in/);
  assert.equal(client.cleared(), true);
});
