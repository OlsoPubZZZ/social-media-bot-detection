"use strict";

const $ = (sel) => document.querySelector(sel);
const LABELS = ["genuine", "suspicious", "spam", "coordinated", "low_confidence"];
let kind = "comments";

// --- form behavior --------------------------------------------------------------

function refreshSourceUI() {
  const source = $("#source").value;
  const isImport = source === "import";
  $("#import-input").classList.toggle("hidden", !isImport);
  $("#target-input").classList.toggle("hidden", isImport);
  $("#enrich").closest("label").classList.toggle("hidden", source !== "youtube");

  // Followers can't come from YouTube.
  const ytOpt = $("#source").querySelector('option[value="youtube"]');
  ytOpt.disabled = kind === "followers";
  if (ytOpt.disabled && source === "youtube") { $("#source").value = "import"; return refreshSourceUI(); }

  const label = source === "youtube"
    ? (kind === "page" ? "Channel id" : "Video id")
    : (kind === "comments" ? "Tweet id" : "User id");
  $("#target-label").textContent = label;
}

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    kind = t.dataset.kind;
    refreshSourceUI();
  })
);
$("#source").addEventListener("change", refreshSourceUI);
$("#file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = () => { $("#data").value = r.result; };
  r.readAsText(f);
});

// --- request --------------------------------------------------------------------

$("#run").addEventListener("click", async () => {
  const source = $("#source").value;
  const keys = {};
  if (source === "youtube") keys.youtube = $("#provider-key").value.trim();
  if (source === "x") keys.x = $("#provider-key").value.trim();
  if ($("#use-llm").checked) keys.anthropic = $("#anthropic-key").value.trim();

  const body = {
    kind, source,
    data: $("#data").value,
    target: $("#target").value,
    keys,
    options: {
      llm: $("#use-llm").checked,
      llm_model: $("#model").value.trim(),
      enrich_authors: $("#enrich").checked,
    },
  };

  const btn = $("#run");
  btn.disabled = true; btn.textContent = "Analyzing…";
  try {
    const res = await fetch("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Request failed");
    render(data);
  } catch (err) {
    $("#results").innerHTML = `<p class="error">⚠ ${escapeHtml(err.message)}</p>`;
  } finally {
    btn.disabled = false; btn.textContent = "Analyze";
  }
});

// --- rendering ------------------------------------------------------------------

function render(data) {
  if (data.kind === "followers") return renderFollowers(data.report);
  if (data.kind === "page") return renderPage(data);
  return renderComments(data);
}

function bars(breakdown) {
  const rows = LABELS.map((l) => {
    const pct = breakdown[l] ?? 0;
    return `<div class="bar-row"><span>${l}</span>
      <div class="bar"><i style="width:${pct}%;background:var(--${l})"></i></div>
      <span>${pct.toFixed(1)}%</span></div>`;
  }).join("");
  return `<div class="bars">${rows}</div>`;
}

function chip(label) {
  return `<span class="chip" style="background:var(--${label})">${label}</span>`;
}

function scoreBlock(score, band, sub) {
  const s = score == null ? "—" : score;
  return `<div class="score-big">${s}<span class="score-sub"> / 100</span></div>
    <div class="score-sub">${sub}${band ? " · confidence: " + band : ""}</div>`;
}

function renderComments(data) {
  const rep = data.report, auth = data.authenticity, amp = data.amplification;
  const flagged = data.results
    .filter((r) => r.label !== "genuine" && r.label !== "low_confidence")
    .sort((a, b) => b.score - a.score);

  let html = scoreBlock(auth.authenticity_score, auth.confidence_band, "Authenticity (comments)");
  html += `<p class="summary">${escapeHtml(rep.summary)}</p>`;
  html += bars(rep.breakdown_pct);
  html += ampWarn(amp);
  html += `<h3>Flagged comments (${flagged.length})</h3>`;
  html += flagged.length ? table(flagged) : `<p class="muted">No comments were flagged.</p>`;
  $("#results").innerHTML = html;
  wireRows(flagged);
}

function table(rows) {
  const body = rows.map((r, i) => `
    <tr class="flag" data-i="${i}">
      <td>${r.score.toFixed(2)}</td><td>${chip(r.label)}</td>
      <td>${escapeHtml(r.handle || r.account_id)}</td>
      <td>${escapeHtml((r.text || "").slice(0, 100))}</td>
    </tr>
    <tr class="evidence hidden" data-ev="${i}"><td colspan="4"></td></tr>`).join("");
  return `<table><thead><tr><th>Score</th><th>Label</th><th>Handle</th><th>Text</th></tr></thead><tbody>${body}</tbody></table>`;
}

function wireRows(rows) {
  document.querySelectorAll("tr.flag").forEach((tr) => {
    tr.addEventListener("click", () => {
      const i = tr.dataset.i;
      const ev = document.querySelector(`tr.evidence[data-ev="${i}"]`);
      ev.classList.toggle("hidden");
      if (!ev.firstChild.innerHTML) ev.firstChild.innerHTML = evidenceHtml(rows[i]);
    });
  });
}

function evidenceHtml(r) {
  const sigs = (r.signals || []).map((s) => {
    const bits = Object.entries(s)
      .filter(([k]) => !["name", "score", "weight", "label_hint", "reason"].includes(k))
      .map(([k, v]) => `${k}=${Array.isArray(v) ? v.length + " items" : escapeHtml(String(v))}`)
      .join(", ");
    return `<li><b>${s.name}</b> (${(s.score).toFixed(2)})${bits ? " — " + bits : ""}</li>`;
  }).join("");
  return `<div class="narr">${escapeHtml(r.narration || "")}</div><ul>${sigs}</ul>`;
}

function renderFollowers(rep) {
  let html = scoreBlock(rep.follower_quality_score, rep.confidence_band, "Follower quality");
  html += `<p class="summary">${escapeHtml(rep.summary)}</p>`;
  html += `<p>Likely fake: <b>${rep.likely_fake_pct.toFixed(1)}%</b> (${rep.likely_fake_count}/${rep.total_followers})</p>`;
  html += bars(rep.breakdown_pct);
  if (rep.suspicious_clusters.length) {
    const c = rep.suspicious_clusters
      .map((x) => `${x.size} accounts @ ${escapeHtml(String(x.window_start))}`).join("; ");
    html += `<div class="warn">⚠ ${rep.suspicious_clusters.length} coordinated join-burst cluster(s): ${c}</div>`;
  }
  if (rep.top_suspicious.length) {
    const body = rep.top_suspicious.map((f) => `
      <tr><td>${f.score.toFixed(2)}</td><td>${chip(f.label)}</td>
      <td>${escapeHtml(f.handle || f.account_id)}</td>
      <td>${(f.account_created_at || "?").slice(0, 10)}</td>
      <td>${f.has_avatar === false ? "no" : f.has_avatar ? "yes" : "?"}</td>
      <td>${(f.reasons || []).join(", ")}</td></tr>`).join("");
    html += `<h3>Most suspicious followers</h3><table><thead><tr><th>Score</th><th>Label</th>
      <th>Handle</th><th>Created</th><th>Avatar</th><th>Reasons</th></tr></thead><tbody>${body}</tbody></table>`;
  }
  $("#results").innerHTML = html;
}

function renderPage(data) {
  const amp = data.amplification, auth = data.authenticity;
  let html = scoreBlock(auth.authenticity_score, auth.confidence_band, "Authenticity (page)");
  html += ampWarn(amp);
  if (amp.coordinated_groups.length) {
    html += "<h3>Coordinated groups</h3>";
    html += amp.coordinated_groups.map((g) =>
      `<p>• group of <b>${g.size}</b> accounts via ${g.link_types.join(", ")} (cohesion ${g.cohesion})</p>`).join("");
  }
  $("#results").innerHTML = html;
}

function ampWarn(amp) {
  if (!amp || !amp.amplification_detected) return `<p class="muted">No coordinated amplification detected.</p>`;
  return `<div class="warn">⚠ Amplification detected: ${amp.coordinated_groups.length} coordinated group(s),
    ${amp.repeated_text_clusters.length} repeated-text cluster(s), ${amp.timing_bursts.length} timing burst(s).</div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

refreshSourceUI();
