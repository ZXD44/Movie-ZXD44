// API สำหรับดึงข้อมูลหนังแบบเรียลไทม์
class MoviesAPI {
    constructor() {
        this.baseUrl = 'https://de88.me/';
        this.newMovieUrl = 'https://de88.me/new-movie/';
        this.searchUrl = 'https://de88.me/?s=';
        this.proxyUrl = 'https://api.allorigins.win/raw?url='; // CORS proxy
        this.movies = [];
        this.cache = new Map();
        this.cacheExpiry = 30 * 60 * 1000; // 30 นาที
    }

    // ดึงข้อมูลจากเว็บไซต์ผ่าน proxy
    async fetchFromDE88(endpoint = '', isSearch = false) {
        try {
            // ใช้หลาย proxy เพื่อความมั่นใจ - อัปเดต proxy ใหม่
            const proxies = [
                window.location.origin + '/proxy?url=', // 🚀 Local System Proxy (Best)
                'https://api.codetabs.com/v1/proxy?quest=',
                'https://api.allorigins.win/raw?url=',
                'https://cors-anywhere.herokuapp.com/',
                'https://thingproxy.freeboard.io/fetch/',
                'https://yacdn.org/proxy/',
                'https://cors.bridged.cc/'
            ];

            // เลือก URL ตามประเภท
            let fullUrl;
            if (isSearch) {
                fullUrl = this.searchUrl + encodeURIComponent(endpoint);
            } else if (endpoint) {
                fullUrl = this.baseUrl + endpoint;
            } else {
                fullUrl = this.newMovieUrl; // ใช้หน้าหนังใหม่เป็นหลัก
            }

            // ลอง direct request ก่อน (อาจจะผ่าน)
            try {
                const directResponse = await fetch(fullUrl, {
                    method: 'GET',
                    mode: 'cors',
                    headers: {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    }
                });

                if (directResponse.ok) {
                    const html = await directResponse.text();
                    return html;
                }
            } catch (directError) {
                // Ignore errors
            }

            // ลอง proxy ต่างๆ
            for (let i = 0; i < proxies.length; i++) {
                const proxy = proxies[i];
                try {
                    let proxyUrl;
                    if (proxy.includes('quest=')) {
                        proxyUrl = proxy + encodeURIComponent(fullUrl);
                    } else {
                        proxyUrl = proxy + encodeURIComponent(fullUrl);
                    }

                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 15000); // 15 วินาที

                    const response = await fetch(proxyUrl, {
                        method: 'GET',
                        signal: controller.signal,
                        headers: {
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                        }
                    });

                    clearTimeout(timeoutId);

                    if (response.ok) {
                        const html = await response.text();
                        // ตรวจสอบว่าได้ HTML จริงหรือไม่
                        if (html.length > 1000 && (html.includes('<html') || html.includes('<!DOCTYPE'))) {
                            return html;
                        }
                    }
                } catch (proxyError) {
                    continue;
                }
            }

            throw new Error('All proxies failed');
        } catch (error) {
            return null;
        }
    }

    // แปลง HTML เป็นข้อมูลหนัง
    parseMoviesFromHTML(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const movies = [];

        // เจาะจงไปที่ article tags ในเว็บ de88.me
        const articles = doc.querySelectorAll('article.post, article[id*="post-"]');

        articles.forEach((element, index) => {
            try {
                // 1. หาหัวข้อหนัง
                const titleLink = element.querySelector('.entry-title a, h3 a, h2 a');
                if (!titleLink) return;

                const fullTitle = titleLink.textContent.trim();
                let rawHref = titleLink.getAttribute('href');
                let moviePageUrl;

                if (rawHref.startsWith('http')) {
                    moviePageUrl = rawHref;
                } else {
                    // ป้องกันการเกิด double URL หรืิอ URL ซ้อนกัน
                    try {
                        moviePageUrl = new URL(rawHref, this.baseUrl).href;
                    } catch (e) {
                        moviePageUrl = this.baseUrl.replace(/\/$/, '') + (rawHref.startsWith('/') ? '' : '/') + rawHref;
                    }
                }

                // 2. หารูปภาพ
                let poster = null;
                const img = element.querySelector('.featured-thumb img, img.wp-post-image, img');
                if (img) {
                    const rawSrc = img.getAttribute('src') ||
                        img.getAttribute('data-lazy-src') ||
                        img.getAttribute('data-src') ||
                        img.getAttribute('data-original');

                    const srcset = img.getAttribute('srcset') || img.getAttribute('data-lazy-srcset');

                    if (rawSrc && !rawSrc.includes('data:image')) {
                        poster = rawSrc;
                    } else if (srcset) {
                        poster = srcset.split(',')[0].split(' ')[0];
                    }

                    if (poster) {
                        if (poster.startsWith('//')) {
                            poster = 'https:' + poster;
                        } else if (poster.startsWith('/')) {
                            poster = this.baseUrl.replace(/\/$/, '') + poster;
                        }
                    }
                }

                // 3. สกัดข้อมูล ปี และ คุณภาพ
                const yearMatch = fullTitle.match(/\((\d{4})\)/);
                const year = yearMatch ? yearMatch[1] : '2025';

                let quality = 'HD';
                if (fullTitle.includes('ซูม')) quality = 'ซูม/CAM';
                else if (fullTitle.includes('4K')) quality = '4K UltraHD';

                // 4. สร้างข้อมูลหนังเบื้องต้น
                if (fullTitle) {
                    const stableId = (fullTitle + year).replace(/[^a-zA-Z0-9]/g, '_');
                    movies.push({
                        id: 'movie_' + stableId,
                        title: this.cleanTitle(fullTitle),
                        originalTitle: fullTitle,
                        year: year,
                        poster: poster || 'https://via.placeholder.com/200x280/2d2d2d/666?text=No+Image',
                        quality: quality,
                        moviePageUrl: moviePageUrl,
                        videoUrl: '',
                        genre: this.detectGenre(fullTitle, element),
                        source: 'DE88.me'
                    });
                }
            } catch (err) {
            }
        });

        return movies;
    }

    // ดึง URL วิดีโอจากหน้าหนังโดยตรง
    async fetchDirectVideoUrl(moviePageUrl) {
        try {
            // ปรับ Path ให้ถูกต้อง
            let relativePath = moviePageUrl;
            if (moviePageUrl.includes(this.baseUrl)) {
                relativePath = moviePageUrl.replace(this.baseUrl, '');
            }

            const html = await this.fetchFromDE88(relativePath);
            if (!html) return null;

            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            // 1. ลองหา <video> หรือ <source> ในหน้าหลัก
            const videoTags = doc.querySelectorAll('video source, video');
            for (const v of videoTags) {
                const src = v.src || v.getAttribute('src');
                if (src && (src.includes('.mp4') || src.includes('.m3u8'))) {
                    return src;
                }
            }

            // 2. ถ้าไม่เจอ ลองหา iframe player
            const iframe = doc.querySelector('iframe[src*="embed"], iframe[src*="player"], iframe[src*="dedkub"], iframe[src*="de88"], iframe[src*="api"]');
            if (iframe) {
                let embedUrl = iframe.src;
                if (embedUrl.startsWith('//')) embedUrl = 'https:' + embedUrl;
                if (embedUrl.startsWith('/')) embedUrl = this.baseUrl.replace(/\/$/, '') + embedUrl;

                // พยายาม Bypass เข้าไปดึงไฟล์ใน Embed
                try {
                    const embedHtml = await this.fetchFromDE88(embedUrl);
                    if (embedHtml) {
                        const videoStyles = [
                            /["'](https?:\/\/[^"']+\.(mp4|m3u8)[^"']*)["']/i,
                            /file\s*:\s*["'](https?:\/\/[^"']+)["']/i,
                            /source\s*:\s*["'](https?:\/\/[^"']+)["']/i,
                            /src\s*:\s*["'](https?:\/\/[^"']+)["']/i
                        ];

                        for (const regex of videoStyles) {
                            const match = embedHtml.match(regex);
                            if (match && match[1]) {
                                let foundUrl = match[1];
                                if (foundUrl.includes('.mp4') || foundUrl.includes('.m3u8') || foundUrl.includes('googleusercontent')) {
                                    return foundUrl;
                                }
                            }
                        }

                        // ค้นหาใน Base64
                        const base64Match = embedHtml.match(/atob\(["']([A-Za-z0-9+/=]+)["']\)/);
                        if (base64Match) {
                            try {
                                const decoded = atob(base64Match[1]);
                                if (decoded.includes('http')) return decoded;
                            } catch (e) { }
                        }
                    }
                } catch (err) {
                }

                return embedUrl;
            }

            return null;
        } catch (e) {
            return null;
        }
    }

    // ตรวจสอบรูปภาพ
    isValidMoviePoster(url) {
        if (!url || typeof url !== 'string') return false;
        if (!url.includes('http') && !url.startsWith('//') && !url.startsWith('/')) return false;
        const imageExtensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'];
        const hasImageExt = imageExtensions.some(ext => url.toLowerCase().includes(ext));
        const imagePatterns = ['image', 'img', 'poster', 'thumb', 'cover'];
        const hasImagePattern = imagePatterns.some(pattern => url.toLowerCase().includes(pattern));
        if (!hasImageExt && !hasImagePattern) return false;
        const excludePatterns = ['logo', 'icon', 'avatar', 'profile', 'banner', 'header', 'footer', 'ads', 'advertisement'];
        const isExcluded = excludePatterns.some(pattern => url.toLowerCase().includes(pattern));
        const tooSmallPatterns = ['16x16', '32x32', '64x64', 'favicon'];
        const isTooSmall = tooSmallPatterns.some(pattern => url.toLowerCase().includes(pattern));
        return !isExcluded && !isTooSmall;
    }

    // ทำความสะอาดชื่อหนัง
    cleanTitle(title) {
        return title
            .replace(/^(HD|ซูม|CAM|TS)\s+/i, '')
            .replace(/\s+\(\d{4}\).*$/, '')
            .replace(/\s+ซับไทย.*$/i, '')
            .replace(/\s+เต็มเรื่อง.*$/i, '')
            .replace(/\s+\d+\s*ตอน.*$/i, '')
            .replace(/\s+ซีซั่น.*$/i, '')
            .replace(/\s+Season.*$/i, '')
            .trim();
    }

    // แก้ไข URL รูปภาพ
    fixImageUrl(url) {
        if (!url) return 'https://via.placeholder.com/300x450/666/fff?text=No+Image';
        if (url.startsWith('//')) return 'https:' + url;
        if (url.startsWith('/')) return this.baseUrl.replace(/\/$/, '') + url;
        return url;
    }

    // ตรวจจับหมวดหมู่
    detectGenre(title, element = null) {
        const titleLower = title.toLowerCase();
        const classLower = element ? element.className.toLowerCase() : '';
        if (classLower.includes('category-action') || classLower.includes('category-thriller') || classLower.includes('category-adventure')) return 'Action';
        if (classLower.includes('category-horror') || classLower.includes('category-ghost')) return 'Horror';
        if (classLower.includes('category-comedy')) return 'Comedy';
        if (classLower.includes('category-animation') || classLower.includes('category-anime') || classLower.includes('category-cartoon')) return 'Animation';
        if (titleLower.includes('แอคชั่น') || titleLower.includes('บู๊') || titleLower.includes('action')) return 'Action';
        if (titleLower.includes('ตลก') || titleLower.includes('comedy')) return 'Comedy';
        if (titleLower.includes('ผี') || titleLower.includes('สยอง') || titleLower.includes('horror')) return 'Horror';
        if (titleLower.includes('การ์ตูน') || titleLower.includes('animation')) return 'Animation';
        return 'Drama';
    }

    // ดึงรายการหนังใหม่
    async getPopularMovies() {
        try {
            const html = await this.fetchFromDE88('', false);
            if (html && html.length > 1000) {
                return this.parseMoviesFromHTML(html);
            }
            return [];
        } catch (error) {
            return [];
        }
    }

    async getVideoUrl(moviePageUrl) {
        try {
            let relativePath = moviePageUrl;
            if (moviePageUrl.includes(this.baseUrl)) {
                relativePath = moviePageUrl.replace(this.baseUrl, '');
            }
            const html = await this.fetchFromDE88(relativePath);
            if (!html) return null;
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const videoSelectors = ['video source[src*=".mp4"]', 'iframe[src*=".mp4"]', 'a[href*=".mp4"]', 'video[src*=".mp4"]', 'source[src*=".mp4"]'];
            for (const selector of videoSelectors) {
                const element = doc.querySelector(selector);
                if (element) {
                    const url = element.src || element.href || element.dataset?.src;
                    if (url && url.includes('.mp4')) return url;
                }
            }
            const iframe = doc.querySelector('iframe');
            if (iframe) {
                let src = iframe.src || iframe.getAttribute('src');
                if (src && (src.includes('player') || src.includes('embed'))) return src;
            }
            return null;
        } catch (error) {
            return null;
        }
    }

    async searchMovies(query, page = 1) {
        try {
            const searchParams = page > 1 ? `?s=${encodeURIComponent(query)}&paged=${page}` : `?s=${encodeURIComponent(query)}`;
            const html = await this.fetchFromDE88(searchParams, false);
            if (html && html.length > 1000) {
                return this.parseMoviesFromHTML(html);
            }
            return [];
        } catch (error) {
            return [];
        }
    }

    async getMoviesByCategory(categoryPath, page = 1) {
        try {
            let path = categoryPath;
            if (!path.endsWith('/')) path += '/';
            if (page > 1) path += `page/${page}/`;
            const html = await this.fetchFromDE88(path, false);
            if (html && html.length > 1000) {
                return this.parseMoviesFromHTML(html);
            }
            return [];
        } catch (error) {
            return [];
        }
    }

    async getMovieById(id) {
        const allMovies = await this.getPopularMovies();
        return allMovies.find(movie => movie.id === id);
    }

    async getMoviesByGenre(genre) {
        const allMovies = await this.getPopularMovies();
        return allMovies.filter(movie => movie.genre.toLowerCase().includes(genre.toLowerCase()));
    }

    async getLatestMovies() {
        const allMovies = await this.getPopularMovies();
        return allMovies.filter(movie => parseInt(movie.year) >= 2024).sort((a, b) => b.year - a.year);
    }

    async getTopRatedMovies() {
        const allMovies = await this.getPopularMovies();
        return allMovies.sort((a, b) => parseFloat(b.rating) - parseFloat(a.rating));
    }

    // ดึงหนังจากหน้าอื่นๆ แบบ real-time
    async getMoviesFromPage(pageNumber = 1) {
        try {
            let pageUrl = pageNumber === 1 ? '' : `page/${pageNumber}/`;
            const html = await this.fetchFromDE88(pageUrl, false);
            if (html && html.length > 1000) {
                return this.parseMoviesFromHTML(html);
            }
            return [];
        } catch (error) {
            return [];
        }
    }

    // ดึงหนังจากหลายหน้า แบบ real-time พร้อม progress callback
    async getAllMovies(maxPages = 3, progressCallback = null) {
        const allMovies = [];
        try {
            for (let page = 1; page <= maxPages; page++) {
                if (progressCallback) {
                    progressCallback({
                        current: page,
                        total: maxPages,
                        percentage: Math.round((page / maxPages) * 100),
                        status: `กำลังโหลดหน้า ${page}/${maxPages}...`
                    });
                }
                const pageMovies = await this.getMoviesFromPage(page);
                if (pageMovies.length > 0) {
                    const uniqueMovies = pageMovies.filter(movie =>
                        !allMovies.some(existing => existing.title === movie.title)
                    );
                    allMovies.push(...uniqueMovies);
                }
            }
            return allMovies;
        } catch (error) {
            return allMovies;
        }
    }

    clearCache() {
        this.cache.clear();
    }
}