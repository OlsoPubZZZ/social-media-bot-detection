"use strict";

const $ = (s) => document.querySelector(s);
let kind = "comments";

// ---------- form behavior ----------

function refreshUI() {
  const source = $("#source").value;
  const isImport = source === "import";
  $("#import-input").classList.toggle("hidden", !isImport);
  $("#target-input").classList.toggle("hidden", isImport);
  $("#enrich").closest("label").classList.toggle("hidden", !(source === "youtube" && kind === "comments"));

  // Followers can't come from YouTube.
  const ytOpt = $("#source").querySelector('option[value="youtube"]');
  ytOpt.disabled = kind === "followers";
  if (ytOpt.disabled && source === "youtube") { $("#source").value = "import"; return refreshUI(); }

  const noun = kind === "comments" ? "comments" : "followers";
  $("#paste-label").textContent =
    `Paste the ${noun} here (a spreadsheet/CSV export works great)`;
  $("#format-hint").innerHTML = kind === "comments"
    ? "Tip: export a post's comments to a CSV and paste or upload it. A <code>text</code> column is all you need to start."
    : "Tip: export an account's followers to a CSV and paste or upload it. A <code>handle</code> column is all you need to start.";
  if (!isImport) {
    $("#target-label").textContent = source === "youtube"
      ? "YouTube video link or ID"
      : (kind === "comments" ? "Tweet link or ID" : "X account / user ID");
  }
}

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    kind = t.dataset.kind;
    refreshUI();
  })
);
$("#source").addEventListener("change", refreshUI);
$("#file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const r = new FileReader();
  r.onload = () => { $("#data").value = r.result; };
  r.readAsText(f);
});

// ---------- run ----------

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
  btn.disabled = true; btn.textContent = "Checking…";
  $("#results").innerHTML = '<p class="spin">Checking… this runs on your computer.</p>';
  try {
    const res = await fetch("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong");
    kind === "followers" ? renderFollowers(data) : renderComments(data);
  } catch (err) {
    $("#results").innerHTML = `<p class="error">⚠ ${escapeHtml(err.message)}</p>`;
  } finally {
    btn.disabled = false; btn.textContent = "Check now →";
  }
});

// ---------- rendering ----------

function counts(b, total) {
  const t = total || 1;
  const real = Math.round((b.genuine || 0) / 100 * t);
  const unsure = Math.round((b.low_confidence || 0) / 100 * t);
  const fake = Math.max(0, t - real - unsure);
  return { real, fake, unsure, total: t };
}

function donut(c) {
  const r = c.real / c.total * 100;
  const f = c.fake / c.total * 100;
  const g = `conic-gradient(var(--real) 0 ${r}%, var(--fake) ${r}% ${r + f}%, var(--unsure) ${r + f}% 100%)`;
  return `<div class="donut" style="background:${g}"><div class="center">
    <div class="pct">${Math.round(r)}%</div><div class="pct-lbl">real people</div></div></div>`;
}

function legend(c) {
  const row = (color, label, n) => `<div class="legend-row">
    <span class="dot" style="background:var(--${color})"></span><span>${label}</span>
    <span class="n">${n}</span><span class="lp">${Math.round(n / c.total * 100)}%</span></div>`;
  return `<div class="legend">
    ${row("real", "Real people", c.real)}
    ${row("fake", "Fake / bot / spam", c.fake)}
    ${c.unsure ? row("unsure", "Not sure", c.unsure) : ""}</div>`;
}

function verdict(c, noun) {
  const fp = c.fake / c.total * 100;
  let cls = "good", msg = `Good news — most of these ${noun} look like real people.`;
  if (fp >= 40) { cls = "bad"; msg = `Warning — a large share of these ${noun} look fake, bot, or spam.`; }
  else if (fp >= 15) { cls = "warn"; msg = `Mixed — a noticeable share of these ${noun} look fake or bot-like.`; }
  return `<div class="verdict ${cls}">${msg}</div>`;
}

function aiCard(text) {
  return `<div class="ai-card"><h3>✨ AI explanation</h3><p>${escapeHtml(text)}</p></div>`;
}

function susItem(who, text, reasons, meta) {
  const rs = [...new Set(reasons)].slice(0, 4).map((x) => `<li>${escapeHtml(x)}</li>`).join("");
  return `<div class="sus-item"><div class="sus-head"><span class="who">${escapeHtml(who)}</span>
    ${meta ? `<span class="meta">${escapeHtml(meta)}</span>` : ""}</div>
    ${text ? `<div class="sus-text">“${text}”</div>` : ""}<ul class="reasons">${rs}</ul></div>`;
}

function bucket(label) {
  if (label === "genuine") return "real";
  if (label === "low_confidence") return "unsure";
  return "fake";
}

function renderComments(data) {
  const rep = data.report, amp = data.amplification;
  const c = counts(rep.breakdown_pct, rep.total_comments);
  let html = `<p class="checked">We checked <b>${rep.total_comments}</b> comments.</p>`;
  html += `<div class="result-top">${donut(c)}${legend(c)}</div>`;
  html += verdict(c, "comments");
  if (amp && amp.amplification_detected && amp.coordinated_groups.length) {
    const g = amp.coordinated_groups[0];
    html += `<div class="callout">⚠ Signs of a coordinated bot campaign: a group of
      <b>${g.size}</b> accounts posted the same or very similar thing.</div>`;
  }
  if (data.ai_summary) html += aiCard(data.ai_summary);
  const flagged = (data.results || []).filter((r) => bucket(r.label) === "fake")
    .sort((a, b) => b.score - a.score).slice(0, 12);
  if (flagged.length) {
    html += `<div class="sus"><h3>What looks suspicious (${flagged.length})</h3>`;
    for (const r of flagged) {
      html += susItem(r.handle || r.account_id, escapeHtml((r.text || "").slice(0, 140)),
        plainReasons(r.signals));
    }
    html += `</div>`;
  }
  $("#results").innerHTML = html;
}

function renderFollowers(data) {
  const rep = data.report;
  const c = counts(rep.breakdown_pct, rep.total_followers);
  let html = `<p class="checked">We checked <b>${rep.total_followers}</b> followers.</p>`;
  html += `<div class="result-top">${donut(c)}${legend(c)}</div>`;
  html += verdict(c, "followers");
  if (rep.suspicious_clusters && rep.suspicious_clusters.length) {
    const cl = rep.suspicious_clusters[0];
    html += `<div class="callout">⚠ <b>${cl.size}</b> accounts started following within
      moments of each other — a classic sign of bought followers.</div>`;
  }
  if (data.ai_summary) html += aiCard(data.ai_summary);
  const top = rep.top_suspicious || [];
  if (top.length) {
    html += `<div class="sus"><h3>Most suspicious followers (${top.length})</h3>`;
    for (const f of top) {
      const meta = `joined ${(f.account_created_at || "?").slice(0, 10)} · ` +
        (f.has_avatar === false ? "no profile photo" : "has a photo");
      html += susItem(f.handle || f.account_id, "", followerReasons(f.reasons), meta);
    }
    html += `</div>`;
  }
  $("#results").innerHTML = html;
}

// ---------- plain-English reasons ----------

function attrText(a) {
  if (a.startsWith("new_account")) {
    const d = a.match(/\d+/);
    return d ? `Brand-new account (only ${d[0]} days old)` : "Brand-new account";
  }
  return ({
    no_avatar: "No profile photo",
    empty_bio: "Empty bio",
    no_posts: "Has never posted anything",
    auto_generated_handle: "Random-looking username",
  })[a] || a.replace(/_/g, " ");
}

function plainReasons(signals) {
  const out = [];
  for (const s of signals || []) {
    const e = s.evidence || {};
    switch (s.name) {
      case "duplicate_text":
        out.push(`Posted the same text as ${(e.distinct_accounts || 2) - 1} other account(s)`); break;
      case "timing_burst":
        out.push("Posted in a sudden burst along with many others"); break;
      case "coordination":
        out.push(`Part of a group of ${e.group_size || "several"} accounts acting together`); break;
      case "follow_burst":
        out.push(`Started following at the same moment as ${(e.cluster_size || 2) - 1} others`); break;
      case "ratio_anomaly":
        out.push(`Follows ${e.following} accounts but only ${e.followers} follow back`); break;
      case "account_weakness":
        (e.attributes || []).forEach((a) => out.push(attrText(a))); break;
      case "llm_text_judgment":
        out.push(`AI read the wording as ${e.classification || "suspicious"}`); break;
      default:
        out.push((e.reason || s.name).replace(/_/g, " "));
    }
  }
  return out;
}

const FOLLOWER_REASONS = {
  abnormal_follow_ratio: "Follows far more accounts than follow it back",
  coordinated_follow_burst: "Started following in a coordinated burst",
  weak_or_new_profile: "New or weak profile (no photo, empty bio, or no posts)",
};

function followerReasons(reasons) {
  return (reasons || []).map((r) => FOLLOWER_REASONS[r] || r.replace(/_/g, " "));
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

refreshUI();
