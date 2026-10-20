/* Optional read-only WebMCP bridge for the MyXstack approval timeline.
 * Browser agents may read/navigate the page but MUST NOT dispatch actions.
 * No credential, backend bypass, or polyfill is introduced.
 */
(() => {
  const context = document.modelContext;
  if (!context || typeof context.registerTool !== "function") return;

  const controller = new AbortController();
  const result = (payload) => ({ content: [{ type: "text", text: JSON.stringify(payload) }] });
  const cards = () => Array.from(document.querySelectorAll("#feed .card"));

  function snapshot() {
    return cards().map((card) => {
      const pills = card.querySelectorAll(".card-meta .pill");
      return {
        id: card.dataset.itemId || "",
        title: card.querySelector(".card-head h2")?.textContent || "Untitled",
        posted_by: pills[0]?.textContent || "",
        status: pills[1]?.textContent || "",
        available_actions: Array.from(card.querySelectorAll(".actions button:not(:disabled)"))
          .map((button) => button.textContent || ""),
      };
    });
  }

  const tools = [
    {
      name: "myxstack_list_visible_cards",
      description: "Read rendered MyXstack card titles, statuses and available action labels on the selected timeline. Nothing is executed and no additional account data is fetched.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      execute: async () => result({ cards: snapshot(), count: cards().length }),
    },
    {
      name: "myxstack_focus_card",
      description: "Focus and scroll to a visible MyXstack timeline card by id without approving, rejecting or executing any card action.",
      inputSchema: {
        type: "object",
        properties: { card_id: { type: "string", description: "Card id returned by myxstack_list_visible_cards" } },
        required: ["card_id"],
        additionalProperties: false,
      },
      execute: async ({ card_id } = {}) => {
        if (typeof card_id !== "string" || !card_id || card_id.length > 128) {
          return result({ ok: false, error: "Invalid card_id" });
        }
        const card = cards().find((item) => item.dataset.itemId === card_id);
        if (!card) return result({ ok: false, error: "Card is not visible on the current timeline" });
        card.tabIndex = -1;
        card.focus({ preventScroll: true });
        card.scrollIntoView({ block: "center" });
        return result({ ok: true, card_id });
      },
    },
    {
      name: "myxstack_refresh_timeline",
      description: "Refresh the selected MyXstack timeline using existing browser UI permissions; does not approve, reject or execute actions.",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
      execute: async () => {
        const refresh = window.myxstackTimeline?.refresh;
        if (typeof refresh !== "function") return result({ ok: false, error: "Timeline is not ready" });
        const ok = await refresh();
        return result({ ok: Boolean(ok), status: document.getElementById("status")?.textContent || "" });
      },
    },
  ];

  // Browser support varies; a failed registration must not break the UI.
  void (async () => {
    for (const tool of tools) {
      if (controller.signal.aborted) break;
      try {
        await context.registerTool(tool, { signal: controller.signal });
      } catch (error) {
        console.warn("WebMCP tool " + tool.name + " unavailable:", error);
      }
    }
  })();
  window.addEventListener("pagehide", () => controller.abort(), { once: true });
})();
