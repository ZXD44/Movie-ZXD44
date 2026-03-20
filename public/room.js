const params = new URLSearchParams(window.location.search);
const roomId = params.get('id');
let vPlayer = document.getElementById('vPlayer');
let vSource = document.getElementById('vSource');
const sid = Math.random().toString(36).substring(7);
let username = localStorage.getItem('zm_username') || 'Guest';
let roomData = null;
let isInternalUpdate = false;

async function init() {
    if (!roomId) { window.location.href = '/'; return; }
    await fetchRoomData();
    if (roomData && roomData.creator === username) {
        document.getElementById('lockControlArea').style.display = 'flex';
        document.getElementById('closeRoomBtn').style.display = 'block';
        document.getElementById('switchSourceBtn').style.display = 'block';
    }
    setInterval(fetchRoomData, 1500);
    setInterval(sendHeartbeat, 5000);
    
    document.getElementById('chatIn').onkeypress = (e) => { if(e.key === 'Enter') sendChat(); };
    
    setInterval(() => { if (roomData && roomData.creator === username) pushUpdate(); }, 2000);
}

async function fetchRoomData() {
    try {
        const resp = await fetch('/api/rooms');
        const rooms = await resp.json();
        const current = rooms[roomId];
        if (!current) return;

        document.getElementById('uCount').textContent = Object.keys(current.participants || {}).length;

        const stateChanged = !roomData || current.videoUrl !== roomData.videoUrl;
        const chatChanged = !roomData || (current.chat || []).length !== (roomData.chat || []).length;
        const emojiChanged = !roomData || (current.emojis || []).length !== (roomData.emojis || []).length;

        if (stateChanged || chatChanged || emojiChanged) applySync(current);
        else roomData = current;
    } catch (e) { }
}

function applySync(newData) {
    if (isInternalUpdate) return;
    const oldData = roomData;
    roomData = newData;
    const isCreator = roomData.creator === username;

    document.getElementById('roomDisplay').textContent = roomData.roomName;
    document.getElementById('movieDisplay').textContent = roomData.movieTitle || "スタンドバイ...";
    
    const lockStatusUI = document.getElementById('lockStatusUI');
    lockStatusUI.textContent = roomData.isLocked ? '🔒' : '🔓';
    lockStatusUI.style.color = roomData.isLocked ? 'var(--danger)' : 'var(--accent)';
    
    // Update menu toggle if it exists
    const lockToggle = document.getElementById('lockToggle');
    if (lockToggle) lockToggle.checked = roomData.isLocked;

    if (!oldData || oldData.videoUrl !== roomData.videoUrl) {
        const isEmbed = roomData.videoUrl.includes('embed') || roomData.videoUrl.includes('player') || roomData.videoUrl.includes('dedkub') || roomData.videoUrl.includes('de88');
        if (isEmbed && !roomData.videoUrl.includes('.mp4')) {
            document.getElementById('playerContent').innerHTML = `<iframe src="${roomData.videoUrl}" frameborder="0" allowfullscreen sandbox="allow-forms allow-scripts allow-same-origin allow-presentation"></iframe>`;
            vPlayer = null;
        } else {
            document.getElementById('playerContent').innerHTML = `<video id="vPlayer" controls playsinline style="width:100%; height:100%;"><source id="vSource" src="${roomData.videoUrl}" type="video/mp4"></video>`;
            vPlayer = document.getElementById('vPlayer');
            vPlayer.load();
        }
    }

    if (roomData.chat) {
        const chatBox = document.getElementById('chatBox');
        const chatHtml = roomData.chat.map(m => {
            const isMe = m.user === username;
            return `<div class="msg-bubble ${isMe?'own':''}">
                ${isMe ? '' : `<div class="msg-user">${m.user}</div>`}
                <div>${m.text}</div>
            </div>`;
        }).join('');
        if (chatBox.innerHTML !== chatHtml) {
            chatBox.innerHTML = chatHtml;
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }

    if (roomData.emojis) {
        if (!window._renderedEmojis) window._renderedEmojis = new Set();
        roomData.emojis.forEach(e => {
            const id = `e_${e.ts}_${e.sid}`;
            if (!window._renderedEmojis.has(id)) {
                spawnEmoji(e.emoji);
                window._renderedEmojis.add(id);
            }
        });
    }
}

async function pushUpdate(immediate = false) {
    if (!roomData || roomData.creator !== username) return;
    isInternalUpdate = true;
    const payload = { id: roomId, videoUrl: roomData.videoUrl, isLocked: roomData.isLocked };
    try { await fetch('/api/update_room', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); } catch (e) { }
    setTimeout(() => { isInternalUpdate = false; }, 500);
}

function sendChat() {
    const input = document.getElementById('chatIn');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    fetch('/api/update_room', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: roomId, newChat: { user: username, text: text, ts: Date.now() } }) });
}

function blastEmoji(emoji) {
    spawnEmoji(emoji);
    fetch('/api/update_room', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: roomId, newEmoji: { emoji: emoji, ts: Date.now(), sid: sid } }) });
}

function spawnEmoji(emoji) {
    const el = document.createElement('div'); el.className = 'floating-emoji'; el.textContent = emoji;
    el.style.left = Math.random() * 80 + 10 + '%'; document.getElementById('emojiLayer').appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

async function sendHeartbeat() { try { await fetch('/api/update_room', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: roomId, heartbeat: username }) }); } catch (e) { } }
function toggleMenu() { const m = document.getElementById('roomMenu'); m.style.display = m.style.display==='flex'?'none':'flex'; }
function closePopup() { document.getElementById('customPopup').classList.remove('show'); }
function showStatus(t) { const s = document.getElementById('statusMsg'); document.getElementById('statusTxt').textContent = t; s.style.opacity = '1'; setTimeout(() => s.style.opacity = '0', 3000); }

function showSourcePicker() {
    if (!roomData || !roomData.allSources) return;
    const sources = roomData.allSources.map((s, i) => `
        <div onclick="switchSource('${s}')" style="cursor: pointer; padding: 14px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 18px; margin-bottom: 10px; display: flex; align-items: center; gap: 15px; transition: all 0.2s;">
            <div style="width: 40px; height: 40px; background: var(--glass); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">🎬</div>
            <div style="flex: 1; text-align: left;">
                <div style="font-weight: 800; font-size: 0.9rem; color: #fff;">แหล่งรับชมสำรอง ${i+1}</div>
                <div style="font-size: 0.7rem; color: var(--text-dim);">คุณภาพมาตรฐานพรีเมียม</div>
            </div>
            <div style="color: var(--accent); font-size: 1.2rem;">⚡</div>
        </div>
    `).join('');
    showPopup('🎬 เปลี่ยนช่องดูหนัง', `<div style="max-height: 400px; overflow-y: auto; padding: 5px 2px;">${sources}</div>`);
}
async function switchSource(url) { closePopup(); roomData.videoUrl = url; await pushUpdate(true); location.reload(); }

function showAdblockPopup() {
    const list = [
        { name: 'AdBlock — ปลอดภัยที่สุด', url: 'https://chromewebstore.google.com/detail/adblock-%E2%80%94-block-ads-acros/gighmmpiobklfepjocnamgkkbiglidom', icon: '✋' },
        { name: 'uBlock Origin Lite — เบาสุด', url: 'https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh', icon: '🛡️' },
        { name: 'Ghostery — ความเป็นส่วนตัว', url: 'https://chromewebstore.google.com/detail/ghostery-privacy-adblocke/mlomiejdfkolichcflejclcbmpeaniij', icon: '👻' }
    ];

    const html = `
        <div style="text-align: left; margin-top: 10px;">
            <p style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 20px;">เพื่อให้ดูได้ลื่นไหลที่สุด แนะนำติดตั้งตัวบล็อกโฆษณาครับ:</p>
            ${list.map(ex => `
                <a href="${ex.url}" target="_blank" style="text-decoration: none; display: flex; align-items: center; gap: 15px; padding: 15px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 18px; margin-bottom: 12px; transition: all 0.2s; color: #fff;">
                    <div style="width: 40px; height: 40px; background: rgba(255,255,255,0.05); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">${ex.icon}</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 800; font-size: 0.9rem;">${ex.name}</div>
                        <div style="font-size: 0.7rem; color: #4ade80;">แตะเพื่อเปิด Chrome Store 🚀</div>
                    </div>
                </a>
            `).join('')}
        </div>
    `;
    showPopup('🛡️ เลือกติดตั้ง AdBlocker', html);
}

function shareRoom() {
    const url = window.location.href;
    navigator.clipboard.writeText(url);
    showStatus("📋 คัดลอกลิงก์เรียบร้อย!");
}

async function closeRoom() {
    showPopup('🗑️ ยืนยันการลบห้อง?', 
        `<div style="margin-bottom: 25px; font-size: 0.95rem;">คุณแน่ใจหรือไม่ว่าต้องการลบห้องนี้ถาวร? เพื่อนทุกคนจะถูกตัดการเชื่อมต่อทันที</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <button onclick="closePopup()" style="background: var(--glass); border: 1px solid var(--border); color: var(--text-dim); padding: 14px; border-radius: 14px; font-weight: 700; cursor: pointer;">ยกเลิก</button>
            <button class="action-btn" onclick="confirmDeleteRoom()" style="background: var(--danger); box-shadow: 0 8px 20px rgba(239,68,68,0.3); border:none; padding: 14px;">ลบถาวร 🗑️</button>
        </div>`,
        true
    );
}

async function confirmDeleteRoom() {
    await fetch('/api/delete_room', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: roomId, user: username }) });
    window.location.href = '/';
}

function showParticipants() {
    if (!roomData || !roomData.participants) return;
    const users = Object.keys(roomData.participants).map(name => {
        const isMe = name === username;
        return `
            <div style="padding: 14px 18px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; transition: all 0.2s;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 38px; height: 38px; background: ${isMe ? 'linear-gradient(135deg, var(--primary), var(--secondary))' : 'rgba(255,255,255,0.1)'}; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">👤</div>
                    <span style="font-weight: 700; font-size: 0.95rem; color: #f8fafc;">${name}</span>
                </div>
                ${isMe ? '<span style="background: var(--primary); color: white; font-size: 0.65rem; font-weight: 900; padding: 4px 8px; border-radius: 6px; box-shadow: 0 0 15px var(--primary-glow);">YOU</span>' : ''}
            </div>
        `;
    }).join('');
    showPopup('👥 คนในห้อง', `<div style="max-height: 400px; overflow-y: auto; padding: 5px 2px;">${users}</div>`);
}

function showPopup(title, text, hideBtn = false) {
    document.getElementById('popupTitle').textContent = title;
    document.getElementById('popupText').innerHTML = text;
    const okBtn = document.getElementById('popupOkBtn');
    if (okBtn) okBtn.style.display = hideBtn ? 'none' : 'flex';
    document.getElementById('customPopup').classList.add('show');
}

async function toggleLock() {
    if (!roomData || roomData.creator !== username) return;
    const isLocked = document.getElementById('lockToggle').checked;
    roomData.isLocked = isLocked;
    await pushUpdate(true);
}

init();
