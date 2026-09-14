// Kage Web Console Frontend Controller

let currentInstance = "";
let streamInterval = null;
let isStreaming = false;

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  fetchInstances();
  setupEventListeners();
});

function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
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

  // Shell execution
  const shellInput = document.getElementById("shell-cmd-input");
  const execBtn = document.getElementById("btn-exec-shell");
  const runShell = async () => {
    const cmd = shellInput.value.trim();
    if (!cmd || !currentInstance) return;
    const termOutput = document.getElementById("terminal-output");
    termOutput.textContent += `\n$ ${cmd}\n`;
    shellInput.value = "";
    try {
      const resp = await fetch(`/api/v1/instances/${currentInstance}/shell/exec`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: cmd }),
      });
      const data = await resp.json();
      if (data.stdout) termOutput.textContent += data.stdout;
      if (data.stderr) termOutput.textContent += `[stderr] ${data.stderr}\n`;
      termOutput.scrollTop = termOutput.scrollHeight;
    } catch (err) {
      termOutput.textContent += `[Error: ${err.message}]\n`;
    }
  };
  execBtn.addEventListener("click", runShell);
  shellInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runShell();
  });

  // Screen streaming and clicks
  const screenImg = document.getElementById("screen-img");
  screenImg.addEventListener("click", async (e) => {
    if (!currentInstance) return;
    const rect = screenImg.getBoundingClientRect();
    const scaleX = 1280 / rect.width;
    const scaleY = 800 / rect.height;
    const x = Math.round((e.clientX - rect.x) * scaleX);
    const y = Math.round((e.clientY - rect.y) * scaleY);

    try {
      await fetch(`/api/v1/instances/${currentInstance}/gui/click`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ x, y, button: 1 }),
      });
      setTimeout(refreshScreenshot, 150);
    } catch (err) {
      console.error("Click error:", err);
    }
  });

  screenImg.addEventListener("mousemove", (e) => {
    const rect = screenImg.getBoundingClientRect();
    const scaleX = 1280 / rect.width;
    const scaleY = 800 / rect.height;
    const x = Math.round((e.clientX - rect.x) * scaleX);
    const y = Math.round((e.clientY - rect.y) * scaleY);
    document.getElementById("mouse-coords").textContent = `(${x}, ${y})`;
  });

  document.getElementById("btn-screenshot-snapshot").addEventListener("click", refreshScreenshot);

  const toggleBtn = document.getElementById("btn-toggle-stream");
  toggleBtn.addEventListener("click", () => {
    if (isStreaming) {
      clearInterval(streamInterval);
      isStreaming = false;
      toggleBtn.textContent = "▶ Auto-Refresh";
    } else {
      isStreaming = true;
      toggleBtn.textContent = "⏸ Pause Refresh";
      streamInterval = setInterval(refreshScreenshot, 1000);
    }
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
        data.steps.forEach(s => {
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
      refreshScreenshot();
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

    list.forEach(inst => {
      const opt = document.createElement("option");
      opt.value = inst.name;
      opt.textContent = `${inst.name} (${inst.status})`;
      select.appendChild(opt);
    });

    if (!currentInstance || !list.find(i => i.name === currentInstance)) {
      currentInstance = list[0].name;
    }
    select.value = currentInstance;
    updateInstanceView();
  } catch (err) {
    console.error("Failed fetching instances:", err);
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
      <p><strong>SSH Port:</strong> <code>${p.ssh || 'N/A'}</code> (ssh kage@127.0.0.1 -p ${p.ssh || 2222})</p>
      <p><strong>VNC Port:</strong> <code>${p.vnc || 'N/A'}</code></p>
      <p><strong>noVNC Port:</strong> <code>${p.novnc || 'N/A'}</code></p>
      <p><strong>Guest Agent Port:</strong> <code>${p.guest_agent || 'N/A'}</code></p>
      <p><strong>Host Bridge API:</strong> <code>${p.api || 'N/A'}</code></p>
      <p><strong>Shared Directory:</strong> ${inst.shared_dir || 'None'}</p>
    `;

    // Refresh display
    refreshScreenshot();
  } catch (err) {
    console.error("Error updating view:", err);
  }
}

async function refreshScreenshot() {
  if (!currentInstance) return;
  const screenImg = document.getElementById("screen-img");
  const placeholder = document.getElementById("screen-placeholder");
  const timestamp = new Date().getTime();
  const url = `/api/v1/instances/${currentInstance}/gui/screenshot?t=${timestamp}`;

  const testImg = new Image();
  testImg.onload = () => {
    screenImg.src = url;
    screenImg.style.display = "block";
    placeholder.style.display = "none";
  };
  testImg.onerror = () => {
    // If not reachable yet
  };
  testImg.src = url;
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
    viewer.textContent = `Error loading accessibility tree: ${err.message}`;
  }
}
