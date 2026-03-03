let token = localStorage.getItem('host_token');
let code = localStorage.getItem('room_code');

async function api(path, method='GET', body=null) {
  const res = await fetch(path, {
    method,
    headers: {'Content-Type':'application/json'},
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok) throw new Error((await res.json()).detail || 'Request failed');
  return res.json();
}

async function createRoom() {
  const host_name = document.getElementById('hostName').value;
  const data = await api('/api/room/create', 'POST', {host_name});
  token = data.token; code = data.code;
  localStorage.setItem('host_token', token);
  localStorage.setItem('room_code', code);
  document.getElementById('create').classList.add('hidden');
  document.getElementById('room').classList.remove('hidden');
  document.getElementById('code').textContent = code;
  document.getElementById('joinUrl').textContent = `${location.origin}/play`;
}

async function startGame() { await api('/api/host/start','POST',{token,target:''}); }
async function resetGame() { await api('/api/host/reset','POST',{token,target:''}); }
async function advance() { await api('/api/host/advance','POST',{token,target:''}); }

function renderSeatEditor(players) {
  return `<h3>Seat order (drag and drop)</h3>
  <p class="muted">Drag a player card to reorder seats, then click <b>Save circle seats</b>.</p>
  <ul id="seatList" class="seat-list">
    ${players.map((p, index) => `
      <li class="seat-item" draggable="true" data-player-id="${p.id}">
        <span class="seat-number">#${index + 1}</span>
        <span>${p.name} (${p.id.slice(0,6)})</span>
      </li>
    `).join('')}
  </ul>`;
}

function setupSeatDragAndDrop() {
  const seatList = document.getElementById('seatList');
  if (!seatList) return;

  let draggingItem = null;

  seatList.querySelectorAll('.seat-item').forEach((item) => {
    item.addEventListener('dragstart', () => {
      draggingItem = item;
      item.classList.add('dragging');
    });

    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      draggingItem = null;
    });

    item.addEventListener('dragover', (event) => {
      event.preventDefault();
    });

    item.addEventListener('drop', (event) => {
      event.preventDefault();
      if (!draggingItem || draggingItem === item) return;

      const listItems = Array.from(seatList.children);
      const draggingIndex = listItems.indexOf(draggingItem);
      const targetIndex = listItems.indexOf(item);

      if (draggingIndex < targetIndex) {
        seatList.insertBefore(draggingItem, item.nextSibling);
      } else {
        seatList.insertBefore(draggingItem, item);
      }

      updateSeatNumbers();
    });
  });
}

function updateSeatNumbers() {
  document.querySelectorAll('#seatList .seat-item').forEach((item, index) => {
    const label = item.querySelector('.seat-number');
    if (label) label.textContent = `#${index + 1}`;
  });
}

async function saveSeatOrder() {
  const ordered_ids = Array.from(document.querySelectorAll('#seatList .seat-item'))
    .map((item) => item.dataset.playerId)
    .filter(Boolean);
  await api('/api/host/seats','POST',{token,ordered_ids});
}

async function saveSettings() {
  await api('/api/host/settings','POST',{
    token,
    morning_s: parseInt(document.getElementById('morning').value,10),
    discussion_s: parseInt(document.getElementById('discussion').value,10),
    nomination_s: parseInt(document.getElementById('nomination').value,10),
    runoff_s: parseInt(document.getElementById('runoff').value,10),
  });
}

async function kick(playerId) {
  await api('/api/host/kick','POST',{token,target:playerId});
}

async function poll() {
  if (!token || !code) return;
  try {
    const state = await api(`/api/state/${code}?token=${encodeURIComponent(token)}`);
    document.getElementById('create').classList.add('hidden');
    document.getElementById('room').classList.remove('hidden');
    document.getElementById('code').textContent = code;
    const announcement = state.host_announcement || {text: ''};
    const players = state.players.map(p => `<div class="card">#${p.seat+1} ${p.name} ${p.alive ? '' : '☠️'} ${p.connected ? '🟢' : '🔴'} <button onclick="kick('${p.id}')">Kick</button></div>`).join('');
    document.getElementById('state').innerHTML = `
      <p>Phase: <b>${state.phase}</b> | Cycle ${state.cycle} | Timer: ${state.seconds_left ?? '-'}s</p>
      <div class="card">
        <h3>Host announcement</h3>
        <p>${announcement.text || 'No announcement.'}</p>
      </div>
      <div class="grid">${players}</div>
      ${renderSeatEditor(state.players)}
      <p>Morning: ${state.morning_deaths.length ? state.morning_deaths.join(', ') : 'No deaths'}</p>`;
    setupSeatDragAndDrop();
  } catch (e) { console.error(e); }
}

setInterval(poll, 1500);
poll();
