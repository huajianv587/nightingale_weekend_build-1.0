
let token=null, clinicId=null, selected=null, ws=null;

function setStatus(m){document.getElementById("authStatus").innerText=m}

async function login(){
  const email=document.getElementById("email").value;
  const password=document.getElementById("password").value;
  const r=await fetch("/api/auth/login",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
  if(!r.ok){setStatus("Login failed");return}
  const d=await r.json(); token=d.token; setStatus("Logged in");
  await refreshTickets();
}

async function refreshTickets(){
  const r=await fetch(`/api/clinician/tickets?token=${encodeURIComponent(token)}`);
  const d=await r.json(); clinicId=d.clinic_id;
  renderTickets(d.tickets); connectWS();
}

function connectWS(){
  if(ws) ws.close();
  ws=new WebSocket(`ws://${location.host}/ws/clinic/${clinicId}?token=${encodeURIComponent(token)}`);
  ws.onopen=()=>ws.send("ping");
  ws.onmessage=(e)=>{
    const m=JSON.parse(e.data);
    if(m.type==="ticket_created" || m.type==="ticket_closed"){ refreshTickets(); }
  };
  setInterval(()=>{try{ws.send("ping")}catch(e){}},4000);
}

function renderTickets(tickets){
  const box=document.getElementById("tickets"); box.innerHTML="";
  tickets.forEach(t=>{
    const div=document.createElement("div");
    div.className="ticket"; div.onclick=()=>selectTicket(t);
    div.innerHTML=`<b>Ticket #${t.id}</b> (risk=${t.risk_level})<br/><small>thread=${t.thread_id} patient=${t.patient_id}</small><br/>${(t.triage_summary||[]).slice(0,3).map(escapeHtml).join("<br/>")}`;
    box.appendChild(div);
  });
}

function selectTicket(t){
  selected=t; document.getElementById("ticketDetail").innerText=JSON.stringify(t,null,2);
}

async function sendReply(){
  if(!selected) return;
  const text=document.getElementById("replyText").value; document.getElementById("replyText").value="";
  const r=await fetch(`/api/clinician/reply?token=${encodeURIComponent(token)}`,{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({ticket_id:selected.id,text})});
  document.getElementById("replyStatus").innerText=r.ok?"Sent":"Failed";
  await refreshTickets();
}

function escapeHtml(s){return (s||"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");}
