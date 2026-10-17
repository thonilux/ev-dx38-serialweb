const channelColors = ['#c3ef68', '#67c4b1', '#e69b68', '#c38adc'];
let toastTimer;

function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2300);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
  return data;
}

function renderChannels(channels) {
  const root = document.querySelector('#channels');
  root.replaceChildren();
  for (let channel = 1; channel <= 4; channel += 1) {
    const values = channels[channel] || channels[String(channel)] || {};
    const level = Number(values.level ?? 0);
    const muted = Boolean(values.muted);
    const card = document.createElement('article');
    card.className = 'channel';
    card.style.setProperty('--channel-color', channelColors[channel - 1]);
    card.innerHTML = `
      <div class="channel-head"><div><div class="channel-index">OUTPUT / 0${channel}</div><div class="channel-name">${values.name || `OUT ${channel}`}</div></div><span class="channel-state ${muted ? 'muted' : ''}">${muted ? 'MUTED' : 'READY'}</span></div>
      <div class="meter"><div class="meter-fill" style="width:${Math.max(0, Math.min(100, (level + 80) / 92 * 100))}%"></div></div>
      <div class="level-row"><div><span class="level-value">${level.toFixed(1)}</span><span class="level-unit">dB</span></div><span class="section-kicker">OUTPUT LEVEL</span></div>
      <input class="range" type="range" min="-80" max="12" step="0.5" value="${level}" aria-label="Output ${channel} level">
      <div class="range-labels"><span>-80 dB</span><span>+12 dB</span></div>
      <div class="channel-actions"><span>STATE HELD IN SESSION</span><button class="mute-button ${muted ? 'is-muted' : ''}" type="button">${muted ? 'UNMUTE' : 'MUTE'}</button></div>`;
    const slider = card.querySelector('.range');
    slider.addEventListener('change', async () => {
      try {
        await api('/api/level', { method: 'POST', body: JSON.stringify({ channel, level: Number(slider.value) }) });
        showToast(`Output ${channel} level updated in staging state`);
        await loadState();
      } catch (error) { showToast(error.message); }
    });
    card.querySelector('.mute-button').addEventListener('click', async () => {
      try {
        await api('/api/mute', { method: 'POST', body: JSON.stringify({ channel, muted: !muted }) });
        showToast(`Output ${channel} mute updated in staging state`);
        await loadState();
      } catch (error) { showToast(error.message); }
    });
    root.append(card);
  }
}

async function loadState() {
  try {
    const [state, health] = await Promise.all([api('/api/state'), api('/api/health')]);
    renderChannels(state.channels || {});
    document.querySelector('#device-name').textContent = state.device_name || 'EV Dx38';
    document.querySelector('#updated-at').textContent = `State refreshed ${new Date().toLocaleTimeString()}`;
    document.querySelector('#connection-label').textContent = health.serial_connected ? 'Device connected' : 'Device offline';
    document.querySelector('#connection-dot').classList.toggle('online', health.serial_connected);
  } catch (error) {
    document.querySelector('#connection-label').textContent = 'Server unavailable';
    document.querySelector('#connection-dot').classList.remove('online');
    showToast(error.message);
  }
}

document.querySelector('#refresh').addEventListener('click', loadState);
loadState();
