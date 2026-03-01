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
async function advance() { await api('/api/host/advance','POST',{token,target:''}); }

function renderSeatEditor(players) {
  return `<h3>Seat order (drag not implemented; comma-separated IDs)</h3>
  <div class="card">${players.map(p=>`${p.name} (${p.id.slice(0,6)})`).join(' → ')}</div>
  <input id="seatOrder" value="${players.map(p=>p.id).join(',')}" />`;
}

async function saveSeatOrder() {
  const ordered_ids = document.getElementById('seatOrder').value.split(',').map(s=>s.trim()).filter(Boolean);
  await api('/api/host/seats','POST',{token,ordered_ids});
}

async function poll() {
  if (!token || !code) return;
  try {
    const state = await api(`/api/state/${code}?token=${encodeURIComponent(token)}`);
    document.getElementById('create').classList.add('hidden');
    document.getElementById('room').classList.remove('hidden');
    document.getElementById('code').textContent = code;
    const players = state.players.map(p => `<div class="card">#${p.seat+1} ${p.name} ${p.alive ? '' : '☠️'}</div>`).join('');
    document.getElementById('state').innerHTML = `
      <p>Phase: <b>${state.phase}</b> | Cycle ${state.cycle}</p>
      <div class="grid">${players}</div>
      ${renderSeatEditor(state.players)}
      <p>Morning: ${state.morning_deaths.length ? state.morning_deaths.join(', ') : 'No deaths'}</p>`;
  } catch (_) {}
}

setInterval(poll, 1500);
poll();
