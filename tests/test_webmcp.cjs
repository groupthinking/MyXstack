const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../ui/webmcp.js"), "utf8");

function makeCard(id, title, status = "unread") {
  const card = {
    dataset: { itemId: id },
    querySelector: (selector) => selector === ".card-head h2" ? { textContent: title } : null,
    querySelectorAll: (selector) => selector === ".card-meta .pill"
      ? [{ textContent: "agent" }, { textContent: status }]
      : selector === ".actions button:not(:disabled)" ? [{ textContent: "Approve" }] : [],
    focus: () => { card.focused = true; },
    scrollIntoView: () => { card.scrolled = true; },
  };
  return card;
}
async function setup(supported = true) {
  const registered = [];
  const cards = [makeCard("a-1", "Research card"), makeCard("b-2", "Review card")];
  let refreshCount = 0;
  const status = { textContent: "2 cards loaded" };
  const document = {
    // Test double only: these tests do not establish native browser support.
    modelContext: supported ? {
      registerTool: async (tool, { signal }) => {
        if (signal.aborted) return;
        registered.push(tool);
        signal.addEventListener("abort", () => {
          const index = registered.indexOf(tool);
          if (index !== -1) registered.splice(index, 1);
        }, { once: true });
      },
    } : undefined,
    querySelectorAll: selector => selector === "#feed .card" ? cards : [],
    getElementById: id => id === "status" ? status : null,
  };
  const window = new EventTarget();
  window.myxstackTimeline = { refresh: async () => { refreshCount++; return true; } };
  vm.runInNewContext(source, { document, window, AbortController, console });
  for (let i = 0; i < 8; i++) await Promise.resolve();
  return { registered, cards, window, get refreshCount() { return refreshCount; } };
}
const output = response => JSON.parse(response.content[0].text);

test("unsupported browser registers no tools", async () => {
  assert.equal((await setup(false)).registered.length, 0);
});
test("registers only three read/navigation tools", async () => {
  const { registered } = await setup();
  assert.deepEqual(registered.map(x => x.name), [
    "myxstack_list_visible_cards", "myxstack_focus_card", "myxstack_refresh_timeline"
  ]);
  for (const tool of registered) {
    assert.equal(tool.inputSchema.type, "object");
    assert.equal(tool.inputSchema.additionalProperties, false);
    assert.ok(!/approve|reject|execute_action/i.test(tool.name));
  }
});
test("lists visible card metadata only, never credentials", async () => {
  const { registered } = await setup();
  const data = output(await registered[0].execute({}));
  assert.equal(data.count, 2);
  assert.deepEqual(data.cards.map(x => x.id), ["a-1", "b-2"]);
  assert.equal(data.cards[0].title, "Research card");
  assert.deepEqual(data.cards[0].available_actions, ["Approve"]);
  assert.ok(!JSON.stringify(data).includes("token"));
});
test("focus scrolls to card without clicking approval", async () => {
  const { registered, cards } = await setup();
  assert.equal(output(await registered[1].execute({ card_id: "b-2" })).ok, true);
  assert.equal(cards[1].focused, true);
  assert.equal(cards[1].scrolled, true);
  assert.equal(output(await registered[1].execute({ card_id: "missing" })).ok, false);
  assert.equal(output(await registered[1].execute({ card_id: null })).ok, false);
});
test("refresh delegates to the existing UI function", async () => {
  const state = await setup();
  const data = output(await state.registered[2].execute({}));
  assert.equal(data.ok, true);
  assert.equal(state.refreshCount, 1);
  assert.equal(data.status, "2 cards loaded");
});

function pageHide(window, persisted) {
  const event = new Event("pagehide");
  Object.defineProperty(event, "persisted", { value: persisted });
  window.dispatchEvent(event);
}

test("bfcache pagehide preserves tools across repeated cached navigations", async () => {
  const state = await setup();
  pageHide(state.window, true);
  assert.equal(state.registered.length, 3);
  pageHide(state.window, true);
  assert.equal(state.registered.length, 3);
  assert.equal(output(await state.registered[0].execute({})).count, 2);
});

test("non-persisted pagehide unregisters all tools", async () => {
  const state = await setup();
  pageHide(state.window, false);
  assert.equal(state.registered.length, 0);
});

test("final disposal after bfcache still unregisters tools", async () => {
  const state = await setup();
  pageHide(state.window, true);
  assert.equal(state.registered.length, 3);
  pageHide(state.window, false);
  assert.equal(state.registered.length, 0);
});
