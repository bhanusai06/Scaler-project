const el = {
    taskSelect: document.getElementById('task-id-select'),
    resetBtn: document.getElementById('reset-btn'),
    refreshBtn: document.getElementById('refresh-btn'),
    submitBtn: document.getElementById('submit-btn'),
    clearTimelineBtn: document.getElementById('clear-timeline-btn'),
    actionInput: document.getElementById('input-action'),
    actionForm: document.getElementById('action-form'),
    observationView: document.getElementById('observation-json'),
    debugView: document.getElementById('debug-json'),
    scoreView: document.getElementById('score-val'),
    doneView: document.getElementById('feedback-val'),
    statusBadge: document.getElementById('current-status'),
    stepCount: document.getElementById('step-count'),
    perfLatency: document.getElementById('perf-latency'),
    perfSteps: document.getElementById('perf-steps'),
    perfMaxSteps: document.getElementById('perf-maxsteps'),
    perfReward: document.getElementById('perf-avg'),
    terminalBadge: document.getElementById('terminal-badge'),
    terminalNotice: document.getElementById('terminal-notice'),
    timeline: document.getElementById('timeline-container'),
    toast: document.getElementById('toast'),
};

let isTerminal = false;
let stepHistory = [];

function showToast(message, type = 'error') {
    el.toast.textContent = message;
    el.toast.className = `toast show toast-${type}`;
    setTimeout(() => {
        el.toast.classList.remove('show');
    }, 2500);
}

function selectedTask() {
    const option = el.taskSelect.options[el.taskSelect.selectedIndex];
    return {
        taskId: option?.dataset.taskId,
        instanceId: option?.dataset.instanceId,
        maxSteps: option?.dataset.maxSteps,
    };
}

function buildUrl(path) {
    const sel = selectedTask();
    const q = new URLSearchParams({
        task_id: sel.taskId,
        instance_id: sel.instanceId,
    });
    return `${path}?${q.toString()}`;
}

async function api(path, method = 'GET', body = null) {
    const url = buildUrl(path);
    const t0 = performance.now();

    try {
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: body ? JSON.stringify(body) : undefined,
        });
        el.perfLatency.textContent = Math.round(performance.now() - t0);

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            showToast(payload.detail || `HTTP ${response.status}`);
            return null;
        }
        return payload;
    } catch (error) {
        showToast(error.message);
        return null;
    }
}

function setTerminalState(done) {
    isTerminal = done;
    el.submitBtn.disabled = done;
    el.terminalBadge.classList.toggle('hidden', !done);
    el.terminalNotice.classList.toggle('hidden', !done);
    el.statusBadge.textContent = done ? 'TERMINAL' : 'RUNNING';
}

function renderObservation(observation) {
    if (!observation) {
        return;
    }

    el.observationView.textContent = JSON.stringify(observation, null, 2);
    el.stepCount.textContent = observation.step_count ?? 0;
    el.perfSteps.textContent = observation.step_count ?? 0;
}

function appendTimeline(step, action, reward, done) {
    stepHistory.push({ step, action, reward, done });

    if (stepHistory.length === 1) {
        el.timeline.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'timeline-entry';
    item.innerHTML = [
        `<div class="te-step">Step ${step}</div>`,
        `<div class="te-status">${done ? 'DONE' : 'ACTIVE'}</div>`,
        `<div class="te-intents">Action: ${Number(action).toFixed(3)}</div>`,
        `<div class="te-score">Reward: ${Number(reward).toFixed(3)}</div>`,
    ].join('');

    el.timeline.appendChild(item);
    el.timeline.scrollLeft = el.timeline.scrollWidth;
}

function resetTimeline() {
    stepHistory = [];
    el.timeline.innerHTML = '<div class="timeline-empty">No steps yet. Reset and submit an action.</div>';
}

async function loadTasks() {
    try {
        const response = await fetch('/tasks');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const tasks = await response.json();
        el.taskSelect.innerHTML = '';

        tasks.forEach((task) => {
            const option = document.createElement('option');
            option.value = `${task.task_id}:${task.instance_id}`;
            option.dataset.taskId = task.task_id;
            option.dataset.instanceId = task.instance_id;
            option.dataset.maxSteps = task.max_steps;
            option.textContent = `${task.task_id} | ${task.instance_id} (${task.difficulty})`;
            el.taskSelect.appendChild(option);
        });

        const sel = selectedTask();
        el.perfMaxSteps.textContent = sel.maxSteps || '-';

        el.taskSelect.addEventListener('change', () => {
            const current = selectedTask();
            el.perfMaxSteps.textContent = current.maxSteps || '-';
            resetTimeline();
            setTerminalState(false);
            el.observationView.textContent = '{\n  "message": "Select Reset to initialize this task instance."\n}';
            el.debugView.textContent = '{}';
            el.scoreView.textContent = '-';
            el.doneView.textContent = '-';
        });
    } catch (error) {
        showToast(`Failed to load tasks: ${error.message}`);
    }
}

async function handleReset() {
    const payload = await api('/reset', 'POST');
    if (!payload) {
        return;
    }

    renderObservation(payload.observation);
    el.debugView.textContent = '{}';
    el.scoreView.textContent = '-';
    el.doneView.textContent = 'false';
    el.perfReward.textContent = '-';
    resetTimeline();
    setTerminalState(false);
}

async function handleRefresh() {
    const payload = await api('/state', 'GET');
    if (!payload) {
        return;
    }

    renderObservation(payload.state);
    setTerminalState(Boolean(payload.state?.done));
}

async function handleSubmit(event) {
    event.preventDefault();

    if (isTerminal) {
        showToast('Episode is terminal. Reset to continue.', 'warning');
        return;
    }

    const raw = Number(el.actionInput.value);
    if (Number.isNaN(raw)) {
        showToast('Action must be a number in [-1, 1].');
        return;
    }

    const action = Math.max(-1, Math.min(1, raw));
    const payload = await api('/step', 'POST', { action });
    if (!payload) {
        return;
    }

    renderObservation(payload.observation);
    el.debugView.textContent = JSON.stringify(payload.info || {}, null, 2);
    el.scoreView.textContent = Number(payload.reward).toFixed(3);
    el.doneView.textContent = String(Boolean(payload.done));
    el.perfReward.textContent = Number(payload.reward).toFixed(3);
    appendTimeline(payload.observation.step_count || 0, action, payload.reward || 0, Boolean(payload.done));
    setTerminalState(Boolean(payload.done));
}

window.addEventListener('DOMContentLoaded', async () => {
    await loadTasks();
    resetTimeline();
    el.observationView.textContent = '{\n  "message": "Click Reset to initialize."\n}';
    el.debugView.textContent = '{}';
    el.scoreView.textContent = '-';
    el.doneView.textContent = '-';
});

el.resetBtn.addEventListener('click', handleReset);
el.refreshBtn.addEventListener('click', handleRefresh);
el.actionForm.addEventListener('submit', handleSubmit);
el.clearTimelineBtn.addEventListener('click', resetTimeline);
