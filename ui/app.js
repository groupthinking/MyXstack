/* MyXstack approval timeline.
 *
 * Deliberately dependency-free and build-free: this is a Python repo run
 * via `make run` / docker compose, and the block set it renders is small
 * and closed. If this file outgrows a few hundred lines, that is the
 * signal to reach for a real frontend build rather than to keep growing
 * it by hand.
 */

const POLL_MS = 5000;

const feedEl = document.getElementById("feed");
const statusEl = document.getElementById("status");
const tokenEl = document.getElementById("token");
const userEl = document.getElementById("user-id");

// Kept in localStorage so the token is never baked into the served file.
tokenEl.value = localStorage.getItem("myxstack.token") || "";
userEl.value = localStorage.getItem("myxstack.user") || "default";
tokenEl.addEventListener("change", () => {
  localStorage.setItem("myxstack.token", tokenEl.value.trim());
  refresh();
});
userEl.addEventListener("change", () => {
  localStorage.setItem("myxstack.user", userEl.value.trim() || "default");
  refresh();
});
document.getElementById("refresh").addEventListener("click", refresh);

function headers() {
  const token = tokenEl.value.trim();
  const base = { "Content-Type": "application/json" };
  return token ? { ...base, Authorization: `Bearer ${token}` } : base;
}

function setStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`;
}

// Mirrors is_safe_url() in cards.py. Only http(s) may reach an anchor's href —
// a javascript: URL would run in this origin, where the approval token lives.
function isSafeUrl(value) {
  if (typeof value !== "string") return false;
  try {
    const scheme = new URL(value, window.location.href).protocol;
    return scheme === "http:" || scheme === "https:";
  } catch {
    return false;
  }
}

// Cards with a PATCH in flight. Prevents a double-click from sending two
// competing actions before the first response lands.
const inFlight = new Set();

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function renderBlock(block) {
  const wrap = el("div", "block");
  if (block.label) wrap.appendChild(el("h3", "block-label", block.label));

  switch (block.type) {
    case "text":
      wrap.appendChild(el("p", "block-text", block.text || ""));
      break;

    case "facts": {
      const dl = el("dl", "facts");
      (block.facts || []).forEach((fact) => {
        dl.appendChild(el("dt", null, fact.key));
        dl.appendChild(el("dd", null, fact.value));
      });
      wrap.appendChild(dl);
      break;
    }

    case "table": {
      const scroller = el("div", "table-scroll");
      const table = el("table");
      if ((block.columns || []).length) {
        const head = el("thead");
        const row = el("tr");
        block.columns.forEach((col) => row.appendChild(el("th", null, col)));
        head.appendChild(row);
        table.appendChild(head);
      }
      const body = el("tbody");
      (block.rows || []).forEach((cells) => {
        const row = el("tr");
        cells.forEach((cell) => row.appendChild(el("td", null, cell)));
        body.appendChild(row);
      });
      table.appendChild(body);
      scroller.appendChild(table);
      wrap.appendChild(scroller);
      break;
    }

    case "links": {
      const list = el("ul", "links");
      (block.links || []).forEach((link) => {
        const item = el("li");
        if (isSafeUrl(link.url)) {
          const anchor = el("a", null, link.label);
          anchor.href = link.url;
          anchor.rel = "noopener noreferrer";
          anchor.target = "_blank";
          item.appendChild(anchor);
        } else {
          // Defence in depth: the API rejects these too, but a stored card
          // predating that validation must never become a live href.
          item.appendChild(el("span", null, `${link.label} (unsafe link removed)`));
        }
        list.appendChild(item);
      });
      wrap.appendChild(list);
      break;
    }

    default:
      // An unknown block type must never render as nothing — show the raw
      // payload so content is visible even on an older UI.
      wrap.appendChild(el("pre", "block-raw", JSON.stringify(block, null, 2)));
  }
  return wrap;
}

function renderCard(item) {
  const card = el("article", "card");

  const head = el("header", "card-head");
  head.appendChild(el("h2", null, item.title || "Untitled"));
  const meta = el("div", "card-meta");
  meta.appendChild(el("span", "pill", item.posted_by || "agent"));
  meta.appendChild(el("span", "pill", item.status || "unread"));
  if (item.created_at) {
    meta.appendChild(el("span", "ts", new Date(item.created_at).toLocaleString()));
  }
  head.appendChild(meta);
  card.appendChild(head);

  (item.blocks || []).forEach((block) => card.appendChild(renderBlock(block)));

  // Two different moments close a card, and the gap between them is where a
  // second click used to land: `dispatched_action` is set by the API the
  // instant an action is claimed, `processed_action` only once the dispatcher
  // has executed it. Treat either as closed so the buttons go dead on
  // approval rather than one poll later.
  const dispatched = item.dispatched_action;
  const processed = (item.metadata || {}).processed_action || dispatched;
  const result = (item.metadata || {}).mcp_result;

  if (result) {
    const note = el("p", "result", result);
    card.appendChild(note);
  }

  const actions = item.actions || [];
  if (actions.length) {
    const row = el("div", "actions");
    actions.forEach((action) => {
      const button = el("button", `btn ${action.style || "neutral"}`, action.label);
      if (processed) {
        // Mirror the dispatcher's terminality rule: once an action has been
        // processed the card is closed, and offering another button would
        // promise something the dispatcher will silently skip.
        button.disabled = true;
        button.title = `Already processed: ${processed}`;
      } else {
        button.addEventListener("click", () => takeAction(item, action));
      }
      row.appendChild(button);
    });
    card.appendChild(row);
    if (processed) {
      card.appendChild(el("p", "closed", `Closed — ${processed} already executed.`));
    }
  }

  return card;
}

async function takeAction(item, action) {
  // Reject before sending, not after: a second PATCH would queue a competing
  // action that the dispatcher then has to discard as already-processed.
  if (inFlight.has(item.id)) {
    setStatus("An action on this card is already in flight.", "err");
    return;
  }
  if (action.confirm && !window.confirm(action.confirm)) return;

  inFlight.add(item.id);
  setStatus(`Sending "${action.label}"…`);
  try {
    const response = await fetch(`/v1/timeline/items/${item.id}`, {
      method: "PATCH",
      headers: headers(),
      body: JSON.stringify({ action_id: action.id }),
    });
    // 409 is not a failure: the card was already approved — by another
    // operator, another tab, or an earlier click of this one. Say so plainly
    // and refresh, so the card redraws as closed instead of leaving a red
    // error next to a card that is in exactly the intended state.
    if (response.status === 409) {
      setStatus("Already actioned — someone got there first.", "ok");
      refresh();
      return;
    }
    if (!response.ok) {
      throw new Error(`${response.status} ${await response.text()}`);
    }
    setStatus(`"${action.label}" sent.`, "ok");
    refresh();
  } catch (err) {
    setStatus(`Failed: ${err.message}`, "err");
  } finally {
    inFlight.delete(item.id);
  }
}

async function refresh() {
  const userId = userEl.value.trim() || "default";
  try {
    const response = await fetch(
      `/v1/timeline/users/${encodeURIComponent(userId)}/items`,
      { headers: headers() }
    );
    if (response.status === 401) {
      setStatus("401 — set a valid API token.", "err");
      return;
    }
    if (!response.ok) throw new Error(`${response.status}`);

    const payload = await response.json();
    feedEl.replaceChildren();
    const items = payload.items || [];
    if (!items.length) {
      feedEl.appendChild(el("p", "empty", "No cards yet."));
    } else {
      items.forEach((item) => feedEl.appendChild(renderCard(item)));
    }
    setStatus(`${items.length} card(s) — updated ${new Date().toLocaleTimeString()}`);
  } catch (err) {
    setStatus(`Could not load timeline: ${err.message}`, "err");
  }
}

refresh();
setInterval(refresh, POLL_MS);
