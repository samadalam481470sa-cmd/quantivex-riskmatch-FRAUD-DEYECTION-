"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const casesEl = $("case-grid");
  const selectedEl = $("selected-case");
  const runButton = $("run-button");
  let cases = [];
  let selected = "circular-ring";
  let loading = false;
  const descriptions = {
    allow: "No suspicious behavior detected in this synthetic scenario.",
    review: "Unusual behavior identified. An analyst would investigate these signals.",
    block: "High risk under the prototype policy. No real financial transaction is blocked."
  };

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = String(content);
    return node;
  }

  function drawCases() {
    casesEl.replaceChildren();
    for (const item of cases) {
      const card = element("button", "case-card" + (selected === item.id ? " selected" : ""));
      card.type = "button";
      card.setAttribute("aria-pressed", selected === item.id ? "true" : "false");
      const top = element("div", "case-card-top");
      top.append(element("span", "", item.category.toUpperCase()));
      top.append(element("span", "checkmark", selected === item.id ? "●" : "○"));
      card.append(top, element("div", "case-card-title", item.name), element("div", "case-desc", item.description));
      card.addEventListener("click", () => {
        selected = item.id;
        selectedEl.textContent = item.name;
        drawCases();
      });
      casesEl.append(card);
    }
  }

  function showSignals(data) {
    const list = $("signals");
    list.replaceChildren();
    const values = [
      ...data.behavioral_signals.map((signal) => ({
        code: signal.code, description: signal.explanation, weight: signal.weight, graph: false
      })),
      ...data.temporal_graph_findings.map((finding) => ({
        code: finding.code, description: finding.explanation, weight: finding.score, graph: true
      }))
    ];
    $("signal-count").textContent = String(values.length);
    if (!values.length) {
      list.append(element("div", "empty-state", "No anomalous behavioral or temporal graph signals were found."));
      return;
    }
    for (const item of values) {
      const row = element("div", "signal-row");
      const icon = element("div", "signal-icon" + (item.graph ? " graph" : ""), item.graph ? "◇" : "!");
      const details = element("div", "signal-details");
      details.append(element("div", "signal-code", item.code.replaceAll("_", " ")), element("div", "signal-desc", item.description));
      row.append(icon, details, element("div", "signal-weight", "+" + Number(item.weight).toFixed(1)));
      list.append(row);
    }
  }

  function showTransfers(transfers) {
    const tbody = $("transfers");
    tbody.replaceChildren();
    for (const tx of transfers) {
      const row = element("tr", tx.candidate ? "event-current" : "");
      const cells = [
        element("td", "", "T+" + String(tx.minute).padStart(2, "0") + "m"),
        element("td", "", tx.sender),
        element("td", "arrow-flow", "→"),
        element("td", "", tx.receiver),
        element("td", "amount", "$" + Number(tx.amount).toLocaleString("en-US", {maximumFractionDigits:2}))
      ];
      const roleCell = element("td", "");
      roleCell.append(element("span", "role-tag" + (tx.candidate ? " current" : ""), tx.candidate ? "INVESTIGATED" : "HISTORICAL"));
      row.append(...cells, roleCell);
      tbody.append(row);
    }
  }

  function showDecision(data) {
    const score = Number(data.risk_score);
    $("risk-score").textContent = score.toFixed(1);
    $("baseline").textContent = Number(data.baseline_score).toFixed(2);
    $("model-version").textContent = data.model_version;
    const label = $("decision-label");
    label.className = "decision-label " + data.decision;
    label.textContent = data.decision.toUpperCase();
    $("decision-description").textContent = descriptions[data.decision];
    const color = data.decision === "block" ? "#ff7581" : data.decision === "review" ? "#ffc06a" : "#50e0b5";
    $("score-ring").style.background = "conic-gradient(" + color + " 0deg " + (score * 3.6) + "deg, #283849 " + (score * 3.6) + "deg 360deg)";
    $("engine-status").textContent = "ANALYZED";
    showSignals(data);
    showTransfers(data.transfers);
  }

  async function run() {
    if (loading || !selected) return;
    loading = true;
    runButton.disabled = true;
    runButton.textContent = "Running engine…";
    $("engine-status").textContent = "SCORING";
    try {
      const response = await fetch("/api/v1/demo/investigate/" + encodeURIComponent(selected), { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      showDecision(await response.json());
    } catch (error) {
      $("engine-status").textContent = "ERROR";
      $("decision-description").textContent = "Investigation unavailable: " + error.message + ". Try reloading the page.";
    } finally {
      loading = false;
      runButton.disabled = false;
      runButton.replaceChildren(element("span", "", "◆  Run investigation  →"));
    }
  }

  runButton.addEventListener("click", run);
  async function init() {
    try {
      const response = await fetch("/api/v1/demo/cases", {cache:"no-store"});
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = await response.json();
      cases = data.cases;
      if (!cases.some((item) => item.id === selected)) selected = cases[0]?.id || "";
      if (!selected) throw new Error("No cases configured");
      selectedEl.textContent = cases.find((item) => item.id === selected).name;
      drawCases();
      runButton.disabled = false;
      await run();
    } catch (error) {
      casesEl.replaceChildren(element("div", "loading-note", "Unable to load demo cases: " + error.message));
    }
  }
  init();
})();
