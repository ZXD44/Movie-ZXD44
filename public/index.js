// Extend the MoviesAPI class to include the new detectGenre method
if (typeof MoviesAPI !== 'undefined') {
    MoviesAPI.prototype.detectGenre = function (title, element = null) {
        const titleLower = title.toLowerCase();
        const classLower = (element && element.className) ? element.className.toLowerCase() : '';

        if (classLower.includes('category-action') || classLower.includes('category-thriller') || classLower.includes('category-adventure')) return 'Action';
        if (classLower.includes('category-horror') || classLower.includes('category-ghost')) return 'Horror';
        if (classLower.includes('category-comedy')) return 'Comedy';
        if (classLower.includes('category-animation') || classLower.includes('category-anime') || classLower.includes('category-cartoon')) return 'Animation';

        if (titleLower.includes('action') || titleLower.includes('บู๊') || titleLower.includes('ต่อสู้') || titleLower.includes('thriller') || titleLower.includes('ระทึก') || titleLower.includes('adventure') || titleLower.includes('ผจญภัย')) return 'Action';
        if (titleLower.includes('horror') || titleLower.includes('ผี') || titleLower.includes('สยอง') || titleLower.includes('น่ากลัว')) return 'Horror';
        if (titleLower.includes('comedy') || titleLower.includes('ตลก') || titleLower.includes('ฮา')) return 'Comedy';
        if (titleLower.includes('animation') || titleLower.includes('การ์ตูน') || titleLower.includes('anime') || titleLower.includes('อนิเมะ')) return 'Animation';

        return 'Drama';
    };
}

const moviesAPI = new MoviesAPI();
let allMovies = [];
let selectedMovie = null;
let currentPage = 1;
let isFetching = false;
let searchTimeout = null;
let searchResults = [];

async function init() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').then(() => {
            console.log('Service Worker Registered');
        });
    }

    const savedName = localStorage.getItem('zm_username');
    if (savedName) document.getElementById('userName').value = savedName;

    showSkeletons();

    try {
        allMovies = await moviesAPI.getMoviesFromPage(1);
        displayMovies();
        loadRooms();
        setInterval(loadRooms, 5000);
        setInterval(updateRoomUI, 1000);
    } catch (e) {
        document.getElementById('movieGrid').innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem;">❌ ไม่สามารถโหลดข้อมูลได้ หรือ CORS ติดขัด กรุณารีเฟรชหน้าเว็บ</div>';
    }

    window.onscroll = () => {
        if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 500) {
            if (!isFetching) {
                loadMore();
            }
        }
    };
}

function showSkeletons() {
    const grid = document.getElementById('movieGrid');
    grid.innerHTML = Array(12).fill(0).map(() => `
        <div class="movie-card skeleton" style="height: 350px;"></div>
    `).join('');
}

async function loadMore() {
    isFetching = true;
    currentPage++;

    const genreValue = document.getElementById('genreFilter').value;
    const query = document.getElementById('movieSearch').value.trim();
    const activeSearch = genreValue || query;

    document.getElementById('loadMore').textContent = `⏳ กำลังโหลด${activeSearch ? 'ผลการหา' : ''}หน้า ${currentPage}...`;

    try {
        let newMovies = [];
        if (genreValue) {
            newMovies = await moviesAPI.getMoviesByCategory(genreValue, currentPage);
        } else if (query) {
            newMovies = await moviesAPI.searchMovies(query, currentPage);
        } else {
            newMovies = await moviesAPI.getMoviesFromPage(currentPage);
        }

        if (newMovies.length > 0) {
            const currentList = activeSearch ? searchResults : allMovies;
            const uniqueNew = newMovies.filter(nm => !currentList.some(existing => existing.id === nm.id));

            if (uniqueNew.length > 0) {
                if (activeSearch) {
                    searchResults = [...searchResults, ...uniqueNew];
                } else {
                    allMovies = [...allMovies, ...uniqueNew];
                }
                displayMovies(activeSearch ? searchResults : null);
                document.getElementById('loadMore').textContent = 'เลื่อนลงเพื่อโหลดต่อ';
            } else {
                document.getElementById('loadMore').textContent = '— ไม่พบข้อมูลใหม่เพิ่ม —';
            }
        } else {
            document.getElementById('loadMore').textContent = '— สิ้นสุดรายการ —';
        }
    } catch (err) {
        console.error("LoadMore Error:", err);
        document.getElementById('loadMore').textContent = '⚠️ ลองใหม่อีกครั้ง';
    }
    isFetching = false;
}

let lastRenderKey = "";
function displayMovies(moviesToDisplay = null) {
    const grid = document.getElementById('movieGrid');
    const countEl = document.getElementById('movieCount');
    const genre = document.getElementById('genreFilter').value;
    const query = document.getElementById('movieSearch').value.trim();

    let list = moviesToDisplay || (query ? searchResults : allMovies);

    if (genre && !moviesToDisplay) {
        list = list.filter(m => m.genre === genre);
    }

    const currentKey = list.map(m => m.id).join(',');
    if (currentKey === lastRenderKey && !moviesToDisplay) return;
    lastRenderKey = currentKey;

    countEl.textContent = `พบหนังทั้งหมด ${list.length} เรื่อง`;

    if (list.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: #64748b;">ไม่พบหนังในหมวดหมู่นี้</div>';
        return;
    }

    grid.innerHTML = list.map((m, index) => `
        <div class="movie-card opacity-0 translate-y-4" style="animation: fadeInUp 0.5s ease-out ${index * 0.05}s forwards;" onclick="selectMovie('${m.id}', this)">
            <div class="poster-box">
                <img src="${m.poster}" 
                     loading="lazy" 
                     onload="this.classList.add('loaded')"
                     onerror="this.src='https://via.placeholder.com/200x300/1e293b/94a3b8?text=No+Image'; this.classList.add('loaded')">
            </div>
            <div class="movie-info">
                <div class="m-title" title="${m.title}">${m.title}</div>
                <div class="m-meta">
                    <span>📅 ${m.year}</span>
                    <span class="m-quality">${m.quality}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    const query = document.getElementById('movieSearch').value.trim();
    if (!query) {
        displayMovies();
        document.getElementById('loadMore').style.display = 'block';
        return;
    }

    document.getElementById('loadMore').style.display = 'none';
    searchTimeout = setTimeout(async () => {
        const grid = document.getElementById('movieGrid');
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem;">🔍 กำลังค้นหาเจาะจง: "' + query + '"...</div>';
        searchResults = await moviesAPI.searchMovies(query);
        displayMovies(searchResults);
    }, 800);
}

async function filterLocal() {
    const genreValue = document.getElementById('genreFilter').value;
    const genreText = document.getElementById('genreFilter').options[document.getElementById('genreFilter').selectedIndex].text.split(' ')[1];
    const query = document.getElementById('movieSearch').value.trim();
    const grid = document.getElementById('movieGrid');
    const countEl = document.getElementById('movieCount');

    if (!genreValue) {
        displayMovies();
        document.getElementById('loadMore').style.display = query ? 'none' : 'block';
        return;
    }

    const localMatches = allMovies.filter(m => {
        return m.genre.includes(genreText) || m.originalTitle.toLowerCase().includes(genreText.toLowerCase());
    });

    searchResults = [...localMatches];
    currentPage = 1;
    document.getElementById('loadMore').style.display = 'none';

    if (searchResults.length > 0) {
        displayMovies(searchResults);
        countEl.textContent = `พบ ${searchResults.length} เรื่องในหน้านี้... กำลังโหลดจากหมวด ${genreText} เพิ่ม ⏳`;
    } else {
        countEl.textContent = `กำลังโหลดหนังหมวด ${genreText}... ⏳`;
        grid.innerHTML = Array(8).fill(0).map(() => `<div class="movie-card skeleton" style="height: 350px;"></div>`).join('');
    }

    try {
        const results = await moviesAPI.getMoviesByCategory(genreValue, 1);
        const uniqueRemote = results.filter(r => !searchResults.some(existing => existing.id === r.id));
        searchResults = [...searchResults, ...uniqueRemote];
        displayMovies(searchResults);
        countEl.textContent = `พบหนังแนว ${genreText} ทั้งหมด ${searchResults.length} เรื่อง`;
        document.getElementById('loadMore').style.display = 'block';
    } catch (e) {
        countEl.textContent = `❌ เกิดข้อผิดพลาดในการโหลดหมวดหมู่`;
        displayMovies(searchResults);
    }
}

function selectMovie(id, el) {
    document.querySelectorAll('.movie-card').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    selectedMovie = allMovies.find(m => m.id === id) || searchResults.find(m => m.id === id);
    if (!selectedMovie) return;

    document.getElementById('selPoster').src = selectedMovie.poster || '';
    document.getElementById('selTitle').textContent = selectedMovie.title;
    document.getElementById('rName').value = `ห้องดู ${selectedMovie.title}`;
    document.getElementById('selectedMovieArea').classList.add('show');
}

async function createRoom() {
    const btn = document.getElementById('createRoomBtn');
    const nameInput = document.getElementById('userName');
    const nick = nameInput.value.trim();

    if (!nick || nick === 'Guest') {
        showPopup(' กรุณาระบุชื่อก่อน', 'กรุณาใส่ชื่อของคุณในช่องด้านบนก่อนสร้างห้องครับ');
        nameInput.focus();
        return;
    }
    localStorage.setItem('zm_username', nick);

    btn.disabled = true;
    btn.textContent = '⏳ กำลังสร้างห้อง...';

    try {
        const videoUrl = await moviesAPI.fetchDirectVideoUrl(selectedMovie.moviePageUrl);
        if (!videoUrl) throw new Error('ไม่พบ URL วิดีโอ');

        const roomId = 'room_' + Math.random().toString(36).substring(2, 10);
        const allSources = Array.isArray(videoUrl) ? videoUrl : [videoUrl];

        const roomData = {
            id: roomId,
            roomName: document.getElementById('rName').value || `Room ${selectedMovie.title}`,
            movieTitle: selectedMovie.title,
            moviePoster: selectedMovie.poster,
            moviePageUrl: selectedMovie.moviePageUrl,
            genre: moviesAPI.detectGenre(selectedMovie.title),
            videoUrl: allSources[0],
            allSources: allSources,
            isPlaying: false,
            currentTime: 0,
            creator: nick,
            createdAt: new Date().toISOString(),
            lastActive: Date.now() / 1000
        };

        const response = await fetch('/api/update_room', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(roomData)
        });

        const result = await response.json();
        if (response.ok && result.success) {
            window.location.href = `/room.html?id=${roomId}`;
        } else {
            throw new Error(result.message || 'Failed to create room');
        }
    } catch (e) {
        showPopup('เกิดข้อผิดพลาด', e.message);
        btn.disabled = false;
        btn.textContent = 'เริ่มสร้างห้องเลย! 🚀';
    }
}

let localRooms = [];
async function loadRooms() {
    try {
        const resp = await fetch('/api/rooms');
        const rooms = await resp.json();
        localRooms = Object.entries(rooms).map(([id, data]) => ({ ...data, id: id }));
        updateRoomUI();
    } catch (e) { }
}

function updateRoomUI() {
    const grid = document.getElementById('activeRooms');
    const now = Date.now() / 1000;
    const EXPIRY = 30;
    const activeRooms = localRooms.filter(r => (EXPIRY - (now - (r.lastActive || 0))) > 0);

    if (activeRooms.length === 0) {
        grid.innerHTML = '<div style="padding: 1rem; color: #94a3b8; font-size: 0.9rem;">ยังไม่มีห้องที่กำลังดูอยู่</div>';
        return;
    }

    activeRooms.sort((a, b) => (b.lastActive || 0) - (a.lastActive || 0));
    grid.innerHTML = activeRooms.map(r => {
        const timeLeft = Math.max(0, Math.ceil(EXPIRY - (now - (r.lastActive || 0))));
        const colorClass = timeLeft <= 10 ? '#ef4444' : '#22c55e';
        const lockIcon = r.isLocked ? '🔒' : '🔓';
        const lockColor = r.isLocked ? '#ef4444' : '#22c55e';
        return `
        <div class="room-card" onclick="joinRoom('${r.id}')">
            <div>
                <div style="font-weight: 800; color: #fff; display: flex; align-items: center; gap: 8px;">
                    ${r.roomName} <span style="font-size: 0.8rem; color: ${lockColor}; opacity: 0.8;">${lockIcon}</span>
                </div>
                <div style="font-size: 0.75rem; color: #94a3b8;">👤 โดย: ${r.creator || 'นิรนาม'}</div>
            </div>
            <div style="text-align: right;">
                <div style="color: ${colorClass}; font-size: 0.75rem; font-weight: bold; display: flex; align-items: center; gap: 5px; justify-content: flex-end;">
                    <span style="width: 8px; height: 8px; background: ${colorClass}; border-radius: 50%; display: inline-block;"></span> Live
                </div>
                <div style="font-size: 10px; color: #64748b; margin-top: 5px;">หายใน: ${timeLeft}s</div>
            </div>
        </div>`;
    }).join('');
}

async function joinRoom(id) {
    if (!id || id === 'undefined') return;
    const nameInput = document.getElementById('userName');
    const nick = nameInput.value.trim();

    if (!nick) {
        showPopup('ข้อมูลไม่ครบ', 'กรุณาใส่ชื่อเล่นของคุณก่อนเข้าห้องครับ');
        nameInput.focus();
        return;
    }

    const room = localRooms.find(r => r.id === id);
    if (room && room.isLocked && (room.creator || '').toLowerCase() !== nick.toLowerCase()) {
        showPopup('🔒 ห้องถูกล็อค', 'ห้องนี้ถูกล็อคโดยเจ้าของห้อง\nเฉพาะเจ้าของเท่านั้นที่เข้าได้', 'lock');
        return;
    }

    localStorage.setItem('zm_username', nick);
    window.location.href = `/room.html?id=${id}`;
}

function showPopup(title, text, type = 'info') {
    const icons = { 'success': '🛡️', 'error': '❌', 'warning': '⚠️', 'info': '🔔', 'lock': '🔒' };
    document.getElementById('popupIcon').textContent = icons[type] || icons.info;
    document.getElementById('popupTitle').textContent = title;
    document.getElementById('popupText').innerHTML = text;
    document.getElementById('customPopup').classList.add('show');
}

function closePopup() { document.getElementById('customPopup').classList.remove('show'); }

function showAdblockPopup() {
    const list = [
        { name: 'AdBlock — ปลอดภัยที่สุด', url: 'https://chromewebstore.google.com/detail/adblock-%E2%80%94-block-ads-acros/gighmmpiobklfepjocnamgkkbiglidom', icon: '✋' },
        { name: 'uBlock Origin Lite — เบาสุด', url: 'https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh', icon: '🛡️' },
        { name: 'Ghostery — ความเป็นส่วนตัว', url: 'https://chromewebstore.google.com/detail/ghostery-privacy-adblocke/mlomiejdfkolichcflejclcbmpeaniij', icon: '👻' }
    ];

    const html = `
        <div style="text-align: left; margin-top: 10px;">
            <p style="font-size: 0.9rem; color: #94a3b8; margin-bottom: 20px;">เลือกติดตั้งตัวใดตัวหนึ่งเพื่อบล็อกโฆษณาในเว็บหนังครับ:</p>
            ${list.map(ex => `
                <a href="${ex.url}" target="_blank" style="text-decoration: none; display: flex; align-items: center; gap: 15px; padding: 15px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 18px; margin-bottom: 12px; transition: all 0.2s; color: #fff;">
                    <div style="width: 40px; height: 40px; background: rgba(255,255,255,0.05); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">${ex.icon}</div>
                    <div style="flex: 1;">
                        <div style="font-weight: 800; font-size: 0.9rem;">${ex.name}</div>
                        <div style="font-size: 0.7rem; color: #4ade80;">แตะเพื่อเปิด Chrome Store 🚀</div>
                    </div>
                </a>
            `).join('')}
            <div style="margin-top: 15px; font-size: 0.75rem; text-align: center; color: var(--text-dim);">*เมื่อติดตั้งแล้ว ให้รีเฟรชหน้าเว็บอีกครั้งครับ</div>
        </div>
    `;
    showPopup('🛡️ เลือกติดตั้ง AdBlocker', html);
}

init();
