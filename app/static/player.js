let token = localStorage.getItem('player_token');
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

async function joinRoom() {
  code = document.getElementById('code').value.toUpperCase();
  const name = document.getElementById('name').value;
  const data = await api('/api/room/join','POST',{code,name});
  token = data.token;
  localStorage.setItem('player_token', token);
  localStorage.setItem('room_code', code);
  document.getElementById('game').classList.remove('hidden');
}

async function rejoinRoom() {
  code = document.getElementById('code').value.toUpperCase() || localStorage.getItem('room_code');
  token = localStorage.getItem('player_token');
  await api('/api/room/rejoin','POST',{code,token});
  document.getElementById('game').classList.remove('hidden');
}

async function act(path, target) {
  await api(path,'POST',{token,target});
}

async function vote(choice) {
  await api('/api/day/vote','POST',{token,choice});
}

function actionButtons(state) {
  const living = state.players.filter(p => p.alive);
  const targetButtons = (endpoint) => living.map(p => `<button onclick="act('${endpoint}','${p.id}')">${p.name}</button>`).join('');

  if (!state.you.alive) return '<p>You are eliminated.</p>';
  if (state.phase === 'night_mimic' && state.you.role === 'mimicophase') return `<h3>Mimic target</h3>${targetButtons('/api/night/mimic')}`;
  if (state.phase === 'night_captain' && state.you.role === 'captain') return `<h3>Captain inspect</h3>${targetButtons('/api/night/captain')}`;
  if (state.phase === 'night_doctor' && state.you.role === 'doctor') return `<h3>Doctor protect</h3>${targetButtons('/api/night/doctor')}`;
  if (state.phase === 'nomination') return `<h3>Nominate</h3>${targetButtons('/api/day/nominate')}`;
  if (state.phase === 'runoff') return `<h3>Vote runoff</h3>${state.runoff_candidates.map(c=>`<button onclick=\"vote('${c.id}')\">${c.name}</button>`).join('')}`;
  if (state.phase === 'single_nominee') return `<button onclick="vote('execute')">Execute</button><button onclick="vote('reject')">Reject</button>`;
  return '<p>Waiting...</p>';
}

async function poll() {
  if (!token || !code) return;
  try {
    const state = await api(`/api/state/${code}?token=${encodeURIComponent(token)}`);
    document.getElementById('game').classList.remove('hidden');
    document.getElementById('roomCode').textContent = state.code;
    document.getElementById('playerState').innerHTML = `
      <p>You: <b>${state.you.name}</b> | Role: <b>${state.you.role ?? 'hidden'}</b></p>
      <p>Phase: <b>${state.phase}</b> | Winner: ${state.winner ?? '-'}</p>
      <p>Mimic teammates: ${state.you.teammates.join(', ') || '-'}</p>
      <p>Morning deaths: ${state.morning_deaths.join(', ') || 'No deaths'}</p>
    `;
    document.getElementById('actions').innerHTML = actionButtons(state);
  } catch (e) {
    console.error(e);
  }
}

setInterval(poll, 1500);
poll();
