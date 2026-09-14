// Kage Web Console Frontend Controller with noVNC Integration

import RFB from "/static/novnc/core/rfb.js";

let currentInstance = "";
let rfb = null;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  fetchInstances();
  fetchAvailableModels();
  setupEventListeners();
});

async function fetchAvailableModels() {
  try {
    const resp = await fetch("/api/v1/instances/default/agent/models");
    const data = await resp.json();
    const select = document.getElementById("agent-model-select");
    if (data.models && data.models.length > 0) {
      select.innerHTML = "";
      data.models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === data.default_model) {
          opt.selected = true;
        }
        select.appendChild(opt);
      });
    }
  } catch (err) {
    console.debug("Could not fetch models dynamically:", err);
  }
}

function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

function setupEventListeners() {
  const instSelect = document.getElementById("instance-select");
  instSelect.addEventListener("change", (e) => {
    currentInstance = e.target.value;
    updateInstanceView();
  });

  document.getElementById("btn-refresh-status").addEventListener("click", fetchInstances);
  document.getElementById("btn-reconnect-vnc").addEventListener("click", () => {
    if (currentInstance) connectVNC(currentInstance);
  });

  document.getElementById("btn-fullscreen").addEventListener("click", () => {
    const container = document.getElementById("screen-container");
    if (!document.fullscreenElement) {
      container.requestFullscreen().catch(err => console.error(err));
    } else {
      document.exitFullscreen();
    }
  });

  // Shell execution
  const shellInput = document.getElementById("shell-cmd-input");
  const execBtn = document.getElementById("btn-exec-shell");
  const runShell = async () => {
    const cmd = shellInput.value.trim();
    if (!cmd || !currentInstance) return;
    const termOutput = document.getElementById("terminal-output");
    termOutput.textContent += `\n$ ${cmd}\n`;
    shellInput.value = "";
    execBtn.disabled = true;
    execBtn.textContent = "Running...";
    try {
      const resp = await fetch(`/api/v1/instances/${currentInstance}/shell/exec`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd, timeout: 30.0 }),
      });
      const data = await resp.json();
      if (data.stdout) termOutput.textContent += data.stdout;
      if (data.stderr) termOutput.textContent += `[stderr] ${data.stderr}\n`;
      if (!data.stdout && !data.stderr) termOutput.textContent += `[Exit code: ${data.exit_code}]\n`;
      termOutput.scrollTop = termOutput.scrollHeight;
    } catch (err) {
      termOutput.textContent += `[Error: ${err.message}]\n`;
    } finally {
      execBtn.disabled = false;
      execBtn.textContent = "Execute";
    }
  };
  execBtn.addEventListener("click", runShell);
  shellInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runShell();
  });

  // Tree inspector
  document.getElementById("btn-refresh-tree").addEventListener("click", refreshTree);

  // Agent execution
  const agentPromptInput = document.getElementById("agent-prompt-input");
  const runAgentBtn = document.getElementById("btn-run-agent");
  runAgentBtn.addEventListener("click", async () => {
    const prompt = agentPromptInput.value.trim();
    if (!prompt || !currentInstance) return;
    const model = document.getElementById("agent-model-select").value;

    const feed = document.getElementById("agent-steps-feed");
    const userStep = document.createElement("div");
    userStep.className = "agent-step";
    userStep.innerHTML = `
      <div class="step-header" style="color:#f0f6fc;">Task Prompt</div>
      <div class="step-thought">${prompt}</div>
    `;
    feed.appendChild(userStep);
    agentPromptInput.value = "";
    runAgentBtn.disabled = true;
    runAgentBtn.textContent = "Agent Working...";

    try {
      const resp = await fetch(`/api/v1/instances/${currentInstance}/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, model, max_steps: 12 }),
      });
      const data = await resp.json();

      if (data.steps) {
        data.steps.forEach((s) => {
          const stepEl = document.createElement("div");
          stepEl.className = "agent-step";
          let toolHtml = "";
          if (s.tool_name) {
            toolHtml = `<div class="step-tool">${s.tool_name}(${JSON.stringify(s.tool_args || {})})</div>`;
          }
          stepEl.innerHTML = `
            <div class="step-header">Step ${s.step}</div>
            <div class="step-thought">${s.thought || ""}</div>
            ${toolHtml}
          `;
          feed.appendChild(stepEl);
        });
      }

      const finalEl = document.createElement("div");
      finalEl.className = "agent-step";
      finalEl.style.borderColor = "var(--accent-color)";
      finalEl.innerHTML = `
        <div class="step-header">Completed</div>
        <div class="step-thought">${data.final_answer}</div>
      `;
      feed.appendChild(finalEl);
      feed.scrollTop = feed.scrollHeight;
    } catch (err) {
      const errEl = document.createElement("div");
      errEl.className = "agent-step";
      errEl.innerHTML = `<div class="step-header" style="color:var(--danger-color)">Error</div><div class="step-thought">${err.message}</div>`;
      feed.appendChild(errEl);
    } finally {
      runAgentBtn.disabled = false;
      runAgentBtn.textContent = "Run Agent";
    }
  });
}

async function fetchInstances() {
  try {
    const resp = await fetch("/api/v1/instances");
    const list = await resp.json();
    const select = document.getElementById("instance-select");
    select.innerHTML = "";

    if (list.length === 0) {
      select.innerHTML = "<option value=''>No instances found</option>";
      return;
    }

    list.forEach((inst) => {
      const opt = document.createElement("option");
      opt.value = inst.name;
      opt.textContent = `${inst.name} (${inst.status})`;
      select.appendChild(opt);
    });

    // Extract instance from URL path if /view/{name}
    const pathParts = window.location.pathname.split("/");
    if (pathParts[1] === "view" && pathParts[2]) {
      const targetFromUrl = pathParts[2];
      if (list.find((i) => i.name === targetFromUrl)) {
        currentInstance = targetFromUrl;
      }
    }

    if (!currentInstance || !list.find((i) => i.name === currentInstance)) {
      currentInstance = list[0].name;
    }
    select.value = currentInstance;
    updateInstanceView();
  } catch (err) {
    console.error("Failed fetching instances:", err);
  }
}

function connectVNC(instanceName) {
  if (rfb) {
    try {
      rfb.disconnect();
    } catch (e) {}
    rfb = null;
  }

  const container = document.getElementById("screen-container");
  container.innerHTML = "";

  const statusLabel = document.getElementById("screen-status-label");
  statusLabel.textContent = "Connecting to QEMU VNC...";
  statusLabel.style.color = "#58a6ff";

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/vnc/${instanceName}`;

  try {
    rfb = new RFB(container, wsUrl, {
      credentials: { password: "" },
      wsProtocols: ["binary"],
    });

    rfb.scaleViewport = true;
    rfb.resizeSession = false;
    rfb.clipViewport = false;
    rfb.focusOnClick = true;

    rfb.addEventListener("connect", () => {
      console.log("Connected to noVNC session for", instanceName);
      statusLabel.textContent = "Live 60 FPS (Connected)";
      statusLabel.style.color = "#3fb950";
    });

    rfb.addEventListener("disconnect", (e) => {
      console.log("noVNC disconnected:", e);
      statusLabel.textContent = "Disconnected (Retrying...)";
      statusLabel.style.color = "#d29922";
      setTimeout(() => {
        if (currentInstance === instanceName) {
          connectVNC(instanceName);
        }
      }, 2500);
    });

    rfb.addEventListener("capabilities", (e) => {
      console.log("VNC server capabilities:", e.detail);
    });

  } catch (err) {
    console.error("RFB init error:", err);
    statusLabel.textContent = "Error initializing VNC";
    statusLabel.style.color = "#da3633";
  }
}

async function updateInstanceView() {
  if (!currentInstance) return;
  try {
    const resp = await fetch(`/api/v1/instances/${currentInstance}`);
    const inst = await resp.json();

    // Update status badge
    const badge = document.getElementById("instance-status-badge");
    badge.textContent = `● ${inst.status}`;
    badge.className = `badge ${inst.status.toLowerCase()}`;

    // Update metrics
    if (inst.metrics) {
      document.getElementById("metric-cpu").textContent = `${inst.metrics.cpu_percent}%`;
      document.getElementById("metric-ram").textContent = `${inst.metrics.memory_rss_mb} MB`;
    }

    // Update info tab
    const infoDiv = document.getElementById("instance-info-details");
    const p = inst.ports || {};
    infoDiv.innerHTML = `
      <p><strong>Name:</strong> ${inst.name}</p>
      <p><strong>Status:</strong> ${inst.status}</p>
      <p><strong>CPUs:</strong> ${inst.cpus} | <strong>Memory:</strong> ${inst.memory_mb} MB</p>
      <p><strong>SSH Port:</strong> <code>${p.ssh || "N/A"}</code> (<code>ssh kage@127.0.0.1 -p ${p.ssh || 2222}</code>)</p>
      <p><strong>VNC Port:</strong> <code>127.0.0.1:${p.vnc || 5900}</code></p>
      <p><strong>Host Bridge API:</strong> <code>http://127.0.0.1:${p.api || 8000}</code></p>
      <p><strong>Shared Directory:</strong> ${inst.shared_dir || "None"}</p>
    `;

    // Connect noVNC live stream
    connectVNC(currentInstance);
  } catch (err) {
    console.error("Error updating view:", err);
  }
}

async function refreshTree() {
  if (!currentInstance) return;
  const viewer = document.getElementById("tree-viewer");
  viewer.textContent = "Loading accessibility tree...";
  try {
    const resp = await fetch(`/api/v1/instances/${currentInstance}/gui/tree`);
    const data = await resp.json();
    if (data.compact_text) {
      viewer.textContent = data.compact_text;
    } else {
      viewer.textContent = JSON.stringify(data, null, 2);
    }
  } catch (err) {
    viewer.textContent = `Accessibility tree unavailable: ${err.message}`;
  }
}
