const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function dashboard() {
  const elements = new Map();
  function element(selector) {
    if (!elements.has(selector)) elements.set(selector, {
      listeners: {}, dataset: {}, value: '', disabled: false, open: false,
      classList: { toggle() {} },
      addEventListener(event, callback) { this.listeners[event] = callback; },
      showModal() { this.open = true; }, close() { this.open = false; }, focus() {},
    });
    return elements.get(selector);
  }
  element('#notes-form').elements = { notes: element('#notes-text') };
  const context = vm.createContext({
    document: { querySelector: element, querySelectorAll: () => [] },
    location: { href: '/app' },
    fetch: () => new Promise(() => {}),
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/dashboard.js'), 'utf8'), context);
  vm.runInContext(`requests = [{id: 7, personName: 'Test Guest', notes: 'Call back',
    feedbackUrl: 'https://test/guest?t=abc', status: 'sent'}]`, context);
  return { context, element };
}

async function openNotes(app) {
  await app.element('#requests-table').listeners.click({
    preventDefault() {}, target: { closest: () => ({ dataset: { editNotes: '7' } }) },
  });
}

test('notes opens its editor without navigating to feedback', async () => {
  const app = dashboard();
  await openNotes(app);
  assert.equal(app.element('#notes-dialog').open, true);
  assert.equal(app.element('#notes-text').value, 'Call back');
  assert.equal(app.element('#notes-person').textContent, 'Test Guest');
  assert.equal(app.context.location.href, '/app');
});

test('save updates only the notes endpoint and closes the editor', async () => {
  const app = dashboard();
  await openNotes(app);
  let request;
  app.context.fetch = async (url, options) => {
    request = { url, ...options };
    return { ok: true, json: async () => ({ ok: true }) };
  };
  app.element('#notes-text').value = 'Issue resolved';
  await app.element('#notes-form').listeners.submit({
    preventDefault() {}, currentTarget: app.element('#notes-form'),
  });
  assert.equal(request.url, '/api/requests/7/notes');
  assert.equal(request.method, 'PUT');
  assert.equal(JSON.parse(request.body).notes, 'Issue resolved');
  assert.equal(app.element('#notes-dialog').open, false);
  assert.equal(app.context.location.href, '/app');
  assert.match(app.element('#requests-table').innerHTML, /Issue resolved/);
});

test('save failure keeps the text for retry', async () => {
  const app = dashboard();
  await openNotes(app);
  app.context.fetch = async () => { throw new Error('network unavailable'); };
  app.element('#notes-text').value = 'Do not lose this note';
  await app.element('#notes-form').listeners.submit({
    preventDefault() {}, currentTarget: app.element('#notes-form'),
  });
  assert.equal(app.element('#notes-dialog').open, true);
  assert.equal(app.element('#notes-text').value, 'Do not lose this note');
  assert.match(app.element('#notes-message').value, /could not be saved/);
  assert.equal(app.element('#notes-save').disabled, false);
});

test('cancel does not navigate or save', async () => {
  const app = dashboard();
  await openNotes(app);
  app.context.fetch = async () => { assert.fail('Cancel must not save'); };
  app.element('#notes-cancel').listeners.click();
  assert.equal(app.element('#notes-dialog').open, false);
  assert.equal(app.context.location.href, '/app');
});
