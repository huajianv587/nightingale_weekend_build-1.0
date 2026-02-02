let token = null, threadId = null, ws = null;
let wsPingTimer = null;
let pollTimer = null;
let sendingText = false;
let sendingAudio = false;

function setStatus(m){ document.getElementById("authStatus").innerText = m; }

function wsUrl(path){
  const proto = (location.protocol === "https:") ? "wss" : "ws";
  return `${proto}://${location.host}${path}`;
}

function escapeHtml(s){
  return (s || "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;");
}

function appendMessage(m){
  const box = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = `msg ${m.sender_role}`;
  div.innerHTML = `
    <div>${escapeHtml(m.content)}</div>
    <div class="meta">
      role=${m.sender_role} | risk=${m.risk_level || ""} | conf=${m.confidence || ""} | ${escapeHtml(m.risk_reason || "")}
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function renderProfile(p){
  document.getElementById("profile").innerText = JSON.stringify(p || {}, null, 2);
}

async function login(){
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  const r = await fetch("/api/auth/login",{
    method:"POST",
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({email,password})
  });

  if(!r.ok){
    setStatus("Login failed");
    return;
  }

  const d = await r.json();
  token = d.token;
  setStatus("Logged in");

  await loadThread();
  await refresh(true);
  connectWS();
  startPolling();
}

async function loadThread(){
  const r = await fetch(`/api/patient/thread?token=${encodeURIComponent(token)}`);
  const d = await r.json();
  threadId = d.thread_id;
}

function connectWS(){
  try{
    if(ws){ ws.close(); ws = null; }
    if(wsPingTimer){ clearInterval(wsPingTimer); wsPingTimer = null; }

    ws = new WebSocket(wsUrl(`/ws/thread/${threadId}?token=${encodeURIComponent(token)}`));

    ws.onopen = () => {
      try{ ws.send("ping"); } catch(e){}
    };

    ws.onmessage = (e) => {
      // 后端推送格式不确定：尽量兼容
      let msg = null;
      try{ msg = JSON.parse(e.data); } catch(err){ return; }

      if(msg.type === "new_message" && msg.message){
        appendMessage(msg.message);
        if(msg.profile) renderProfile(msg.profile);

        if(msg.escalation_required){
          document.getElementById("escalateBox").classList.remove("hidden");
          document.getElementById("ticketInfo").innerText = msg.ticket_id ? ("Ticket #"+msg.ticket_id) : "";
        }else{
          document.getElementById("escalateBox").classList.add("hidden");
        }
      }
    };

    ws.onclose = () => {
      // 断线后交给轮询兜底
    };

    wsPingTimer = setInterval(()=>{
      try{ ws && ws.readyState === 1 && ws.send("ping"); }catch(e){}
    }, 5000);

  }catch(e){
    // WebSocket失败也没关系，轮询会兜底
  }
}

function startPolling(){
  if(pollTimer) clearInterval(pollTimer);
  // 每2秒拉一次，确保无需刷新页面也能看到新消息
  pollTimer = setInterval(()=>{ refresh(false); }, 2000);
}

async function refresh(clear=false){
  if(!token) return;
  const r = await fetch(`/api/patient/messages?token=${encodeURIComponent(token)}`);
  if(!r.ok) return;

  const d = await r.json();

  if(clear){
    document.getElementById("chat").innerHTML = "";
    (d.messages || []).forEach(appendMessage);
  }else{
    // 简单做法：直接全量重绘，稳定但不最省
    document.getElementById("chat").innerHTML = "";
    (d.messages || []).forEach(appendMessage);
  }

  renderProfile(d.profile);

  // escalation box 同步一下（如果后端在messages里也给了）
  if(d.escalation_required){
    document.getElementById("escalateBox").classList.remove("hidden");
    document.getElementById("ticketInfo").innerText = d.ticket_id ? ("Ticket #"+d.ticket_id) : "";
  }else{
    document.getElementById("escalateBox").classList.add("hidden");
  }
}

async function sendText(){
  if(sendingText) return;
  const input = document.getElementById("text");
  const text = input.value;

  if(!text || !text.trim()) return;

  sendingText = true;
  input.value = "";

  // 1) 先把自己这条消息立刻显示出来（不等WS）
  appendMessage({
    sender_role: "patient",
    content: text,
    risk_level: "low",
    confidence: null,
    risk_reason: ""
  });

  const btn = document.querySelector("button[onclick='sendText()']");
  if(btn) btn.disabled = true;

  try{
    const r = await fetch(`/api/patient/message?token=${encodeURIComponent(token)}`,{
      method:"POST",
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text})
    });

    if(!r.ok){
      // 如果失败，把状态提示出来
      setStatus("Send failed");
      return;
    }

    const d = await r.json();

    if(d.escalation_required){
      document.getElementById("escalateBox").classList.remove("hidden");
      document.getElementById("ticketInfo").innerText = d.ticket_id ? ("Ticket #"+d.ticket_id) : "";
    }

    // 2) 发完主动拉一次最新，保证立刻看到assistant回复/后端写入的最终内容
    await refresh(false);

  }finally{
    sendingText = false;
    if(btn) btn.disabled = false;
  }
}

async function sendAudio(){
  if(sendingAudio) return;

  const fileInput = document.getElementById("audio");
  const f = fileInput.files[0];
  if(!f) return;

  sendingAudio = true;

  const btn = document.querySelector("button[onclick='sendAudio()']");
  if(btn) btn.disabled = true;

  // 先在UI里显示一个“已发送音频”的占位（避免你以为没反应一直点）
  appendMessage({
    sender_role: "patient",
    content: `🎤 Sent audio: ${f.name}`,
    risk_level: "",
    confidence: null,
    risk_reason: ""
  });

  try{
    const fd = new FormData();
    fd.append("file", f, f.name);

    const r = await fetch(`/api/patient/message_audio?token=${encodeURIComponent(token)}`,{
      method:"POST",
      body: fd
    });

    if(!r.ok){
      setStatus("Audio upload failed");
      return;
    }

    const d = await r.json();

    if(d.escalation_required){
      document.getElementById("escalateBox").classList.remove("hidden");
      document.getElementById("ticketInfo").innerText = d.ticket_id ? ("Ticket #"+d.ticket_id) : "";
    }

    // 发完清空选择，避免你点第二次又把同一个文件再发一遍
    fileInput.value = "";

    // 拉取最新：如果后端把“转写文本/assistant回复”写进messages，这里会立刻显示
    await refresh(false);

  }finally{
    sendingAudio = false;
    if(btn) btn.disabled = false;
  }
}

