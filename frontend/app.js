const rows = document.getElementById("rows");
const statusEl = document.getElementById("status");
const emptyEl = document.getElementById("empty");

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function fmt(ts) {
  return ts ? new Date(ts).toLocaleString() : "—";
}

async function load() {
  try {
    const res = await fetch("/api/events?limit=100");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const events = await res.json();

    rows.replaceChildren();
    for (const e of events) {
      const tr = document.createElement("tr");
      tr.append(
        cell(e.machine_id),
        cell(e.material_type),
        cell(e.item_count),
        cell(e.status, `status-${e.status}`),
        cell(e.estimated_weight_g ?? "—"),
        cell(fmt(e.event_timestamp)),
        cell(fmt(e.created_at)),
      );
      rows.append(tr);
    }
    emptyEl.hidden = events.length > 0;
    statusEl.textContent = `${events.length} event(s) · updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    statusEl.textContent = `error: ${err.message}`;
  }
}

document.getElementById("refresh").addEventListener("click", load);
load();
setInterval(load, 5000);
