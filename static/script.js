// static/script.js - 完整版（含饼图等所有函数）
window.selectedGoldPrices = window.selectedGoldPrices || [];
window.selectedRedPrices = window.selectedRedPrices || [];
window.ocrKnownGoldCountFromScreen = window.ocrKnownGoldCountFromScreen || false;

let selectedGoldPrices = window.selectedGoldPrices;
let selectedRedPrices = window.selectedRedPrices;
let goldPricePool = [];
let redPricePool = [];
const ESTIMATED_GOLD_CUTOFF = 6;

function normalizePriceList(values) {
    const list = Array.isArray(values)
        ? values
        : typeof values === 'string'
            ? values.split(/[\s,，]+/).filter(Boolean)
            : values == null
                ? []
                : [values];
    return list
        .map(v => {
            if (v === 'unknown') return 'unknown';
            const n = Number(String(v).replace(/,/g, '').trim());
            return Number.isFinite(n) ? n : null;
        })
        .filter(v => v === 'unknown' || Number.isFinite(v));
}

function normalizeComboPrices(comboInfo) {
    if (!comboInfo) return [];

    let rawPrices = [];
    if (Array.isArray(comboInfo)) {
        rawPrices = comboInfo;
    } else if (Array.isArray(comboInfo.prices)) {
        rawPrices = comboInfo.prices;
    } else if (typeof comboInfo.prices === 'string') {
        rawPrices = comboInfo.prices.split(/[\s,，+]+/);
    } else if (typeof comboInfo.price_str === 'string') {
        rawPrices = comboInfo.price_str.match(/\d[\d,]*/g) || [];
    } else if (typeof comboInfo.combo === 'string') {
        rawPrices = comboInfo.combo.split(/[\s,，+]+/);
    }

    return rawPrices
        .map(v => Number(String(v).replace(/,/g, '').trim()))
        .filter(v => Number.isFinite(v));
}

async function loadPriceOptions() {
    try {
        const response = await fetch('/api/prices');
        const data = await response.json();
        goldPricePool = data.gold_prices || [];
        redPricePool = data.red_prices || [];
        
        const goldSelect = document.getElementById('gold_price_select');
        goldPricePool.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.textContent = p.toLocaleString();
            goldSelect.appendChild(opt);
        });
        
        const redSelect = document.getElementById('red_price_select');
        const memoryRedSelect = document.getElementById('memory_price_select');
        
        const unknownOpt = document.createElement('option');
        unknownOpt.value = 'unknown';
        unknownOpt.textContent = '❓ 未知（计入件数）';
        redSelect.appendChild(unknownOpt);
        
        redPricePool.forEach(p => {
            const opt1 = document.createElement('option');
            opt1.value = p;
            opt1.textContent = p.toLocaleString();
            redSelect.appendChild(opt1);
            
            const opt2 = document.createElement('option');
            opt2.value = p;
            opt2.textContent = p.toLocaleString();
            memoryRedSelect.appendChild(opt2);
        });
        
        const totalSelect = document.getElementById('total_items');
        for (let i = 1; i <= 50; i++) {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = i + ' 件';
            totalSelect.appendChild(opt);
        }
        
        const purpleSelect = document.getElementById('purple_count');
        for (let i = 1; i <= 40; i++) {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = i + ' 件';
            purpleSelect.appendChild(opt);
        }
    } catch (error) {
        console.error('加载选项失败:', error);
    }
}

// ========== 价格推荐 ==========
function suggestGoldPrice(input) {
    const suggestDiv = document.getElementById('gold_suggest');
    if (!input || input.length < 2) {
        suggestDiv.innerHTML = '';
        return;
    }
    const matches = goldPricePool.filter(p => String(p).includes(input)).slice(0, 5);
    suggestDiv.innerHTML = matches.map(p => 
        `<span class="suggest-item" onclick="fillGoldPrice(${p})">${p.toLocaleString()}</span>`
    ).join('');
}

function fillGoldPrice(price) {
    document.getElementById('gold_price_input').value = price;
    document.getElementById('gold_suggest').innerHTML = '';
}

function addGoldPriceManual() {
    const input = document.getElementById('gold_price_input').value.replace(/,/g, '').trim();
    if (!input) return;
    const price = parseInt(input);
    if (isNaN(price)) return;
    if (!goldPricePool.includes(price)) {
        alert(`价格 ${price.toLocaleString()} 不在金色价格池中`);
        return;
    }
    selectedGoldPrices.push(price);
    window.selectedGoldPrices = selectedGoldPrices;
    renderSelectedPrices('gold');
    document.getElementById('gold_price_input').value = '';
    document.getElementById('gold_suggest').innerHTML = '';
}

function suggestRedPrice(input) {
    const suggestDiv = document.getElementById('red_suggest');
    if (!input || input.length < 2) {
        suggestDiv.innerHTML = '';
        return;
    }
    const matches = redPricePool.filter(p => String(p).includes(input)).slice(0, 5);
    suggestDiv.innerHTML = matches.map(p => 
        `<span class="suggest-item" onclick="fillRedPrice(${p})">${p.toLocaleString()}</span>`
    ).join('');
}

function fillRedPrice(price) {
    document.getElementById('red_price_input').value = price;
    document.getElementById('red_suggest').innerHTML = '';
}

function addRedPriceManual() {
    const input = document.getElementById('red_price_input').value.replace(/,/g, '').trim();
    if (!input) return;
    const price = parseInt(input);
    if (isNaN(price)) return;
    selectedRedPrices.push(price);
    window.selectedRedPrices = selectedRedPrices;
    renderSelectedPrices('red');
    document.getElementById('red_price_input').value = '';
    document.getElementById('red_suggest').innerHTML = '';
}

function addRedUnknown() {
    selectedRedPrices.push('unknown');
    window.selectedRedPrices = selectedRedPrices;
    renderSelectedPrices('red');
}

// ========== 原有功能 ==========
function addGoldPrice() {
    const select = document.getElementById('gold_price_select');
    const price = select.value;
    if (!price) return;
    selectedGoldPrices.push(parseInt(price));
    window.selectedGoldPrices = selectedGoldPrices;
    renderSelectedPrices('gold');
    select.value = '';
}

function addRedPrice() {
    const select = document.getElementById('red_price_select');
    const value = select.value;
    if (!value) return;
    if (value === 'unknown') {
        selectedRedPrices.push('unknown');
    } else {
        selectedRedPrices.push(parseInt(value));
    }
    window.selectedRedPrices = selectedRedPrices;
    renderSelectedPrices('red');
    select.value = '';
}

function addBigRedPrice() {
    const input = document.getElementById('red_high_input');
    const value = input.value.trim();
    if (!value) return;
    const price = parseInt(value);
    if (isNaN(price) || price <= 1000000) {
        alert('请输入100万以上的红色价格');
        return;
    }
    selectedRedPrices.push(price);
    window.selectedRedPrices = selectedRedPrices;
    renderSelectedPrices('red');
    input.value = '';
}

function removePrice(type, index) {
    if (type === 'gold') {
        selectedGoldPrices.splice(index, 1);
        window.selectedGoldPrices = selectedGoldPrices;
        renderSelectedPrices('gold');
    } else {
        selectedRedPrices.splice(index, 1);
        window.selectedRedPrices = selectedRedPrices;
        renderSelectedPrices('red');
    }
}

function renderSelectedPrices(type) {
    const container = type === 'gold' 
        ? document.getElementById('gold_selected') 
        : document.getElementById('red_selected');
    const prices = type === 'gold' ? selectedGoldPrices : selectedRedPrices;
    
    if (prices.length === 0) {
        container.innerHTML = '<span style="color:#ccc;font-size:13px;">暂无选择</span>';
        return;
    }
    
    container.innerHTML = prices.map((p, i) => {
        if (p === 'unknown') {
            return `<span class="price-tag" style="background:#f0f0f0;color:#999;border:1px solid #ccc;">
                ❓ 未知 
                <span class="price-tag-remove" onclick="removePrice('${type}', ${i})">×</span>
            </span>`;
        }
        return `<span class="price-tag">
            ${Number(p).toLocaleString()} 
            <span class="price-tag-remove" onclick="removePrice('${type}', ${i})">×</span>
        </span>`;
    }).join('');
}

function setEmptyResults(extraLines) {
    const resultsDiv = document.getElementById('results');
    if (!resultsDiv) return;
    const lines = Array.isArray(extraLines) && extraLines.length > 0
        ? extraLines
        : ['请填写左侧参数后点击分析', '或点击一键扫描自动识别'];
    resultsDiv.innerHTML = `
        <div class="results-empty">
            <div class="results-empty-title">暂无分析结果</div>
            ${lines.map(line => `<div>${line}</div>`).join('')}
        </div>
    `;
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    if (tab === 'analyze') {
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
        document.getElementById('analyze-tab').classList.add('active');
        selectedGoldPrices = window.selectedGoldPrices || [];
        selectedRedPrices = window.selectedRedPrices || [];
        renderSelectedPrices('gold');
        renderSelectedPrices('red');
    } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('memory-tab').classList.add('active');
        loadMemory();
    }
}

function resetForm() {
    document.getElementById('avg').value = '';
    document.getElementById('total_items').value = '0';
    document.getElementById('purple_count').value = '0';
    document.getElementById('gold_total_size').value = '0';
    document.getElementById('known_gold_count').value = '0';
    document.getElementById('known_red_count').value = '0';
    document.getElementById('double_gold').checked = false;
    document.getElementById('red_high_input').value = '';
    document.getElementById('gold_price_input').value = '';
    document.getElementById('red_price_input').value = '';
    document.getElementById('gold_suggest').innerHTML = '';
    document.getElementById('red_suggest').innerHTML = '';
    selectedGoldPrices = [];
    selectedRedPrices = [];
    window.selectedGoldPrices = [];
    window.selectedRedPrices = [];
    window.ocrKnownGoldCountFromScreen = false;
    renderSelectedPrices('gold');
    renderSelectedPrices('red');
    setEmptyResults();
    document.getElementById('loading').style.display = 'none';
}

function applyOCRFields(fields) {
    if (!fields) return;
    const normalizeNumber = (value) => {
        if (value === undefined || value === null || value === '') return '';
        const raw = String(value).replace(/[，\s]/g, '');
        const match = raw.match(/\d[\d,]*(?:\.\d+)?/);
        return match ? match[0].replace(/,/g, '').replace(/\.$/, '') : raw;
    };
    if (fields.avg !== undefined && fields.avg !== null && fields.avg !== '') {
        document.getElementById('avg').value = normalizeNumber(fields.avg);
    }
    if (fields.total_items !== undefined && fields.total_items !== null && fields.total_items !== '') {
        document.getElementById('total_items').value = normalizeNumber(fields.total_items);
    }
    if (fields.purple_count !== undefined && fields.purple_count !== null && fields.purple_count !== '') {
        document.getElementById('purple_count').value = normalizeNumber(fields.purple_count);
    }
    if (fields.gold_total_size !== undefined && fields.gold_total_size !== null && fields.gold_total_size !== '') {
        document.getElementById('gold_total_size').value = normalizeNumber(fields.gold_total_size);
    }
    if (fields.gold_count !== undefined && fields.gold_count !== null && fields.gold_count !== '') {
        document.getElementById('known_gold_count').value = normalizeNumber(fields.gold_count);
        window.ocrKnownGoldCountFromScreen = true;
    }
}

function setLoadingState(message) {
    const loadingEl = document.getElementById('loading');
    if (!loadingEl) return;
    loadingEl.style.display = 'block';
    loadingEl.textContent = message || '识别中...';
}

function clearLoadingState() {
    const loadingEl = document.getElementById('loading');
    if (!loadingEl) return;
    loadingEl.style.display = 'none';
}

async function captureScreenBlob() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        throw new Error('当前浏览器不支持屏幕捕获');
    }

    const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 1 },
        audio: false
    });

    try {
        const video = document.createElement('video');
        video.srcObject = stream;
        video.muted = true;
        await video.play();
        await new Promise((resolve) => {
            if (video.videoWidth && video.videoHeight) {
                resolve();
                return;
            }
            video.onloadedmetadata = () => resolve();
        });

        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 1;
        canvas.height = video.videoHeight || 1;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
        if (!blob) {
            throw new Error('截图失败');
        }
        return blob;
    } finally {
        stream.getTracks().forEach((track) => track.stop());
    }
}

async function ocrFillFromScreen() {
    setLoadingState('正在截取屏幕并识别 金色均价 / 总件数 / 紫色件数 ...');
    try {
        const blob = await captureScreenBlob();
        const formData = new FormData();
        formData.append('image', blob, 'screen.png');

        const response = await fetch('/api/ocr/screen', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (!response.ok || result.error) {
            throw new Error(result.error || '识别失败');
        }

        const fields = result.fields || {};
        applyOCRFields(fields);
        const loadingEl = document.getElementById('loading');
        if (loadingEl) {
            loadingEl.style.display = 'block';
            loadingEl.textContent = '识别完成，已自动填充输入框';
            setTimeout(() => { loadingEl.style.display = 'none'; }, 1800);
        }
    } catch (error) {
        if (error && error.name === 'NotAllowedError') {
            return;
        }
        alert('屏幕识别失败: ' + error.message);
    } finally {
        clearLoadingState();
    }
}

async function analyze() {
    const avg = document.getElementById('avg').value;
    if (!avg) { alert('请输入金色均价'); return; }
    
    selectedGoldPrices = normalizePriceList(window.selectedGoldPrices || []);
    selectedRedPrices = normalizePriceList(window.selectedRedPrices || []);
    window.selectedGoldPrices = selectedGoldPrices.slice();
    window.selectedRedPrices = selectedRedPrices.slice();
    
    console.log('发送的gold_prices:', selectedGoldPrices);
    console.log('发送的red_prices:', selectedRedPrices);
    
    const data = {
        avg: avg,
        total_items: document.getElementById('total_items').value || '0',
        purple_count: document.getElementById('purple_count').value || '0',
        gold_total_size: document.getElementById('gold_total_size').value || '0',
        known_gold_count: document.getElementById('known_gold_count').value || '0',
        known_gold_count_from_ocr: !!window.ocrKnownGoldCountFromScreen,
        known_red_count: document.getElementById('known_red_count').value || '0',
        search_timeout: document.getElementById('search_timeout').value || '20',
        gold_prices: selectedGoldPrices.slice(),
        red_prices: selectedRedPrices.slice(),
        min_red: '0',
        double_gold: document.getElementById('double_gold').checked
    };
    
    const totalItems = parseInt(document.getElementById('total_items').value || '0', 10);
    const timeoutSec = parseInt(document.getElementById('search_timeout').value || '20', 10);
    const loadingEl = document.getElementById('loading');
    loadingEl.style.display = 'block';
    loadingEl.textContent = totalItems >= 8
        ? `⚠️ 计算量较大，超过 ${timeoutSec} 秒将自动截断，请耐心等待...`
        : '搜索中...';
    document.getElementById('results').innerHTML = '';
    setEmptyResults();
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await response.json();
        document.getElementById('loading').style.display = 'none';
        
        const resultsDiv = document.getElementById('results');
        
        if (result.error) {
            resultsDiv.innerHTML = `<p style="text-align:center;margin-top:20px;color:#f44336;">错误: ${result.error}</p>`;
            return;
        }
        
        if (!result.results || result.results.length === 0) {
            const emptyLines = ['未找到匹配的金色组合', '请检查已知条件是否过多或过严'];
            if (result.warning) {
                emptyLines.push(result.warning);
            }
            setEmptyResults(emptyLines);
            return;
        }
        
        let html = `<p style="margin:15px 0;color:#666;font-size:14px;">未知红价参考: 记忆池动态模型（每件约 ${(result.unknown_red_mean||102000).toLocaleString()}） | 共 ${result.total} 种可能`;
        if (result.unknown_red_count > 0) {
            html += ` | <span style="color:#999;">❓ 未知红色: ${result.unknown_red_count}件</span>`;
        }
        if (result.gold_total_size) {
            html += ` | <span style="color:#2196F3;">📐 金色格子总数: ${result.gold_total_size}</span>`;
        }
        if (result.double_gold) html += ' | <span style="color:#ff9800;font-weight:bold;">🔄 超级加倍模式</span>';
        if (result.cached) html += ' | <span style="color:#4CAF50;">⚡缓存</span>';
        html += '</p>';
        if (result.warning) {
            html += `<p style="margin:8px 0 12px;color:#ff9800;font-weight:bold;">${result.warning}</p>`;
        }
        if (result.results.some(r => r.is_estimated) && !result.results.some(r => !r.is_estimated)) {
            html += '<p style="margin:8px 0 12px;color:#ff9800;font-weight:bold;">未找到精确组合，以下为估算结果</p>';
        }
        html += '<table><thead><tr><th>金色件数</th><th>红色件数</th><th>估计总价值<br><span style="font-size:11px;font-weight:normal;">只包含金色和红色藏品</span></th><th>备注</th></tr></thead>';
        
        let exactRows = '';
        let estimatedRows = '';
        let estimatedCount = 0;
        result.results.forEach((r, index) => {
            const cls = r.is_estimated ? 'estimated' : 'exact';
            const note = r.is_estimated ? '估算' : '精确';
            const clickable = r.has_details ? `style="cursor:pointer;color:#2196F3;text-decoration:underline;" onclick="toggleCombos(${index})"` : '';
            let rowHtml = `<tr>
                <td ${clickable}><strong>${r.gold_count}</strong>${r.has_details ? ' 🔍' : ''}</td>
                <td><strong>${r.red_count}</strong></td>
                <td>约 ${r.total_value.toLocaleString()}<br><span style="color:#888;font-size:12px;">区间 ${(r.low_value || r.total_value).toLocaleString()} ~ ${(r.high_value || r.total_value).toLocaleString()}</span></td>
                <td class="${cls}">${note}</td>
            </tr>`;
            if (r.has_details && r.combos && r.combos.length > 0) {
                const title = r.is_truncated 
                    ? `金色组合详情（原始500种已截断，过滤后${r.combo_count}种）` 
                    : `金色组合详情（共${r.combo_count}种）`;
                rowHtml += `<tr id="combos-${index}" style="display:none;" class="combo-detail"><td colspan="4">
                    <strong style="font-size:13px;">${title}:</strong>
                    <div style="margin-top:8px;">`;
                r.combos.forEach((comboInfo, ci) => {
                    const prices = normalizeComboPrices(comboInfo);
                    const total = prices.reduce((a, b) => a + b, 0);
                    const sizeStr = comboInfo.size_str;
                    const totalSize = comboInfo.total_size;
                    rowHtml += `<div class="combo-item">
                        <span class="label">#${ci+1}</span> 
                        [${prices.length ? prices.join(', ') : (comboInfo.price_str || '无可显示价格')}]
                        <span style="color:#666;">总价: ${total.toLocaleString()}</span>
                        <span style="color:#888;">格子: ${sizeStr}=${totalSize}</span>
                    </div>`;
                });
                if (r.is_truncated) {
                    rowHtml += `<div class="combo-item" style="color:#ff9800;font-weight:bold;">⚠️ 原始组合超过500种已截断，过滤后剩余${r.combo_count}种</div>`;
                }
                rowHtml += '</div></td></tr>';
            } else if (r.has_details && r.is_estimated) {
                rowHtml += `<tr id="combos-${index}" style="display:none;" class="combo-detail"><td colspan="4">
                    <strong style="font-size:13px;">${r.gold_count}金估算说明：</strong>
                    <div style="margin-top:8px;color:#555;line-height:1.8;">
                        金色部分：${r.gold_count} 件 × 金色均价<br>
                        红色部分：${r.red_count} 件，按记忆池红价模型估算<br>
                        估值约：${r.total_value.toLocaleString()}（区间 ${(r.low_value||0).toLocaleString()} ~ ${(r.high_value||0).toLocaleString()}）<br>
                        ${ESTIMATED_GOLD_CUTOFF + 1} 件以上只做估算，不展示具体组合。
                    </div>
                </td></tr>`;
            }
            if (r.is_estimated) {
                estimatedRows += rowHtml;
                estimatedCount += 1;
            } else {
                exactRows += rowHtml;
            }
        });
        html += `<tbody id="exact-results-body">${exactRows}</tbody>`;
        if (estimatedRows) {
            const estimatedOpen = exactRows.length === 0;
            html += `<tbody id="extra-estimate-head">
                <tr>
                    <td colspan="4" style="cursor:pointer;text-align:left;color:#2196F3;font-weight:bold;" onclick="toggleExtraEstimate()">
                        <span id="extra-estimate-arrow">${estimatedOpen ? '▼' : '▶'}</span> 金色 ${ESTIMATED_GOLD_CUTOFF + 1} 件以上估算结果（共 ${estimatedCount} 条）
                    </td>
                </tr>
            </tbody>`;
            html += `<tbody id="extra-estimate-body" style="display:${estimatedOpen ? 'table-row-group' : 'none'};">${estimatedRows}</tbody>`;
        }
        html += '</table>';
        if (result.timeout) {
            html += '<p style="text-align:center;margin-top:12px;color:#ff9800;font-weight:bold;">⚠️ 搜索超过设定时间，后续组合已自动截断</p>';
        }
        resultsDiv.innerHTML = html;
    } catch (error) {
        document.getElementById('loading').style.display = 'none';
        alert('请求失败: ' + error.message);
    }
}

function toggleCombos(index) {
    const row = document.getElementById(`combos-${index}`);
    if (row) row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
}

function toggleExtraEstimate() {
    const body = document.getElementById('extra-estimate-body');
    const arrow = document.getElementById('extra-estimate-arrow');
    if (!body || !arrow) return;
    if (body.style.display === 'none') {
        body.style.display = 'table-row-group';
        arrow.textContent = '▼';
    } else {
        body.style.display = 'none';
        arrow.textContent = '▶';
    }
}

function toggleMemoryList() {
    const list = document.getElementById('memory-list');
    const icon = document.getElementById('memory-collapse-icon');
    if (list) {
        if (list.style.display === 'none') {
            list.style.display = 'block';
            icon.textContent = '▼';
        } else {
            list.style.display = 'none';
            icon.textContent = '▶';
        }
    }
}

// ========== 饼图 ==========
function renderPieChart(priceCounts) {
    const container = document.getElementById('pie-chart-container');
    if (!container) return;
    
    const entries = Object.entries(priceCounts);
    const total = entries.reduce((sum, [, count]) => sum + count, 0);
    
    if (total === 0) {
        container.innerHTML = '<p style="text-align:center;color:#999;">无数据</p>';
        return;
    }
    
    const colors = [
        '#F8BBD0', '#BBDEFB', '#FFF9C4', '#C8E6C9', '#D1C4E9',
        '#FFE0B2', '#B2EBF2', '#DCEDC8', '#F0F4C3', '#FFCCBC',
        '#E1BEE7', '#B3E5FC', '#C5E1A5', '#FFE082', '#A5D6A7',
        '#EF9A9A', '#80CBC4', '#CE93D8', '#90CAF9', '#FFCC80',
        '#A5D6A7', '#F48FB1', '#81D4FA', '#C5E1A5', '#FFAB91'
    ];
    
    entries.sort((a, b) => b[1] - a[1]);
    
    const size = 400;
    const center = size / 2;
    const radius = center - 15;
    const hoverOffset = 15;
    const tooltipId = 'pie-' + Date.now();
    
    function generateSVG(hoverIdx) {
        let paths = '';
        let startAngle = -Math.PI / 2;
        entries.forEach(([, count], i) => {
            const angle = (count / total) * 2 * Math.PI;
            const endAngle = startAngle + angle;
            const midAngle = (startAngle + endAngle) / 2;
            let ox = 0, oy = 0;
            if (i === hoverIdx) {
                ox = hoverOffset * Math.cos(midAngle);
                oy = hoverOffset * Math.sin(midAngle);
            }
            const cx = center + ox, cy = center + oy;
            const x1 = cx + radius * Math.cos(startAngle);
            const y1 = cy + radius * Math.sin(startAngle);
            const x2 = cx + radius * Math.cos(endAngle);
            const y2 = cy + radius * Math.sin(endAngle);
            const largeArc = angle > Math.PI ? 1 : 0;
            paths += `<path d="M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z" 
                fill="${colors[i % colors.length]}" stroke="#fff" stroke-width="2"
                style="transition:all .3s ease;${i===hoverIdx?'filter:brightness(.9);':''}"/>`;
            startAngle = endAngle;
        });
        return paths;
    }
    
    function generateLegend(hoverIdx) {
        let html = '';
        entries.forEach(([price, count], i) => {
            const pct = ((count/total)*100).toFixed(1);
            const h = i === hoverIdx;
            html += `<div
                style="display:flex;align-items:center;gap:10px;font-size:${h?'18px':'16px'};margin-bottom:10px;white-space:nowrap;padding:8px 10px;border-radius:8px;cursor:pointer;transition:all .3s ease;${h?'background:#e8e8e8;':''}"
                onmouseenter="pieLegendHover('${tooltipId}',${i})"
                onmouseleave="pieLegendHover('${tooltipId}',-1)"
                onclick="pieLegendClick('${tooltipId}',${i})">
                <span style="width:${h?'22px':'18px'};height:${h?'22px':'18px'};border-radius:5px;background:${colors[i%colors.length]};display:inline-block;flex-shrink:0;"></span>
                <span style="font-weight:bold;color:${h?'#222':'#444'};min-width:80px;">${Number(price).toLocaleString()}</span>
                <span style="color:${h?'#555':'#777'};">${count}次</span>
                <span style="color:#aaa;font-size:${h?'16px':'14px'};">(${pct}%)</span>
            </div>`;
        });
        return html;
    }
    
    container.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;gap:50px;flex-wrap:nowrap;padding:25px;position:relative;overflow-x:auto;">
            <div id="${tooltipId}-pie" style="width:${size}px;height:${size}px;flex-shrink:0;position:relative;cursor:default;">
                <svg id="${tooltipId}-svg" width="${size}" height="${size}">${generateSVG(-1)}</svg>
            </div>
            <div id="${tooltipId}-tooltip" style="position:absolute;display:none;background:rgba(0,0,0,.85);color:#fff;padding:10px 15px;border-radius:8px;font-size:14px;pointer-events:none;z-index:100;"></div>
            <div id="${tooltipId}-legend" style="max-height:400px;overflow-y:auto;padding:15px 20px;background:#fafafa;border-radius:10px;min-width:280px;flex-shrink:0;">${generateLegend(-1)}</div>
        </div>`;
    
    const state = { 
        id: tooltipId,
        entries, total, colors, center, radius, hoverOffset,
        svg: document.getElementById(tooltipId + '-svg'),
        legend: document.getElementById(tooltipId + '-legend'),
        tooltip: document.getElementById(tooltipId + '-tooltip'),
        pie: document.getElementById(tooltipId + '-pie'),
        currentHover: -1
    };
    window['pieState_' + tooltipId] = state;
    
    function updateHover(idx) {
        if (idx !== state.currentHover) {
            state.currentHover = idx;
            state.svg.innerHTML = generateSVG(idx);
            state.legend.innerHTML = generateLegend(idx);
        }
    }
    
    state.pie.addEventListener('mousemove', (e) => {
        const rect = state.pie.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width/2;
        const y = e.clientY - rect.top - rect.height/2;
        let angle = Math.atan2(x, -y) * 180 / Math.PI;
        if (angle < 0) angle += 360;
        const pct = angle / 360 * 100;
        let cum = 0, found = -1;
        for (let i = 0; i < entries.length; i++) {
            const p = (entries[i][1] / total) * 100;
            if (pct >= cum && pct < cum + p) { found = i; break; }
            cum += p;
        }
        if (found >= 0) {
            updateHover(found);
            state.tooltip.innerHTML = `<strong>${Number(entries[found][0]).toLocaleString()}</strong><br>${entries[found][1]}次 (${((entries[found][1]/total)*100).toFixed(1)}%)`;
            state.tooltip.style.display = 'block';
            state.tooltip.style.left = (e.clientX - rect.left + 20) + 'px';
            state.tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
        }
    });
    state.pie.addEventListener('mouseleave', () => {
        state.tooltip.style.display = 'none';
        updateHover(-1);
    });
}

window.pieLegendHover = function(id, idx) {
    const s = window['pieState_' + id];
    if (!s) return;
    s.currentHover = idx;
    s.svg.innerHTML = generateSVGFor(s, idx);
    s.legend.innerHTML = generateLegendFor(s, idx);
};

window.pieLegendClick = function(id, idx) {
    const s = window['pieState_' + id];
    if (!s) return;
    s.currentHover = idx;
    s.svg.innerHTML = generateSVGFor(s, idx);
    s.legend.innerHTML = generateLegendFor(s, idx);
    setTimeout(() => { 
        s.currentHover = -1; 
        s.svg.innerHTML = generateSVGFor(s, -1); 
        s.legend.innerHTML = generateLegendFor(s, -1); 
    }, 800);
};

function generateSVGFor(s, hoverIdx) {
    let paths = '';
    let startAngle = -Math.PI / 2;
    s.entries.forEach(([, count], i) => {
        const angle = (count / s.total) * 2 * Math.PI;
        const endAngle = startAngle + angle;
        const midAngle = (startAngle + endAngle) / 2;
        let ox = 0, oy = 0;
        if (i === hoverIdx) { ox = s.hoverOffset * Math.cos(midAngle); oy = s.hoverOffset * Math.sin(midAngle); }
        const cx = s.center + ox, cy = s.center + oy;
        const x1 = cx + s.radius * Math.cos(startAngle);
        const y1 = cy + s.radius * Math.sin(startAngle);
        const x2 = cx + s.radius * Math.cos(endAngle);
        const y2 = cy + s.radius * Math.sin(endAngle);
        const largeArc = angle > Math.PI ? 1 : 0;
        paths += `<path d="M ${cx} ${cy} L ${x1} ${y1} A ${s.radius} ${s.radius} 0 ${largeArc} 1 ${x2} ${y2} Z" fill="${s.colors[i%s.colors.length]}" stroke="#fff" stroke-width="2" style="transition:all .3s ease;${i===hoverIdx?'filter:brightness(.9);':''}"/>`;
        startAngle = endAngle;
    });
    return paths;
}

function generateLegendFor(s, hoverIdx) {
    let html = '';
    s.entries.forEach(([price, count], i) => {
        const pct = ((count/s.total)*100).toFixed(1);
        const h = i === hoverIdx;
        html += `<div style="display:flex;align-items:center;gap:10px;font-size:${h?'18px':'16px'};margin-bottom:10px;white-space:nowrap;padding:8px 10px;border-radius:8px;cursor:pointer;transition:all .3s ease;${h?'background:#e8e8e8;':''}"
            onmouseenter="pieLegendHover('${s.id}',${i})"
            onmouseleave="pieLegendHover('${s.id}',-1)"
            onclick="pieLegendClick('${s.id}',${i})">
            <span style="width:${h?'22px':'18px'};height:${h?'22px':'18px'};border-radius:5px;background:${s.colors[i%s.colors.length]};display:inline-block;flex-shrink:0;"></span>
            <span style="font-weight:bold;color:${h?'#222':'#444'};min-width:80px;">${Number(price).toLocaleString()}</span>
            <span style="color:${h?'#555':'#777'};">${count}次</span>
            <span style="color:#aaa;font-size:${h?'16px':'14px'};">(${pct}%)</span>
        </div>`;
    });
    return html;
}

// ========== 记忆池 ==========
async function loadMemory() {
    try {
        const res = await fetch('/api/memory');
        const data = await res.json();
        const content = document.getElementById('memory-content');
        if (!data.auctions || data.auctions.length === 0) {
            content.innerHTML = '<p style="text-align:center;margin-top:20px;color:#999;">记忆池为空</p>';
            return;
        }
        let html = `<p style="margin:15px 0;color:#666;">共 <strong>${data.total_auctions}</strong> 次记录</p>`;
        html += `<div class="memory-collapse-header" onclick="toggleMemoryList()"><span id="memory-collapse-icon">▶</span> 📋 记录列表</div>`;
        html += `<div id="memory-list" style="display:none;">`;
        data.auctions.forEach((a, i) => {
            html += `<div class="memory-item"><div class="memory-item-header">
                <span><strong>#${i+1}</strong></span>
                <span style="flex:1;text-align:center;">${a.prices.join(', ')}</span>
                <span style="font-size:12px;color:#999;">${a.time||''}</span>
                <span><button class="btn-edit" onclick="editMemory(${i})">修改</button>
                <button class="btn-delete" onclick="deleteMemory(${i})">删除</button></span>
            </div></div>`;
        });
        html += '</div>';
        html += '<h3>📊 价格分布</h3>';
        html += '<div class="chart-container" id="pie-chart-container"></div>';
        html += `<button class="btn-primary" style="margin-top:20px;" onclick="updateWeights()">用记忆池更新权重</button>`;
        content.innerHTML = html;
        setTimeout(() => renderPieChart(data.price_counts), 100);
    } catch (e) {
        console.error('加载记忆池失败:', e);
    }
}

function addMemoryFromSelect() {
    const select = document.getElementById('memory_price_select');
    const price = select.value;
    if (!price) { alert('请选择红色价格'); return; }
    addMemory([parseInt(price)]);
}

async function addMemory(prices) {
    try {
        const res = await fetch('/api/memory/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prices: prices})
        });
        if (res.ok) loadMemory();
    } catch (e) { alert('请求失败: ' + e.message); }
}

async function deleteMemory(idx) {
    if (!confirm('确认删除？')) return;
    try {
        await fetch(`/api/memory/delete/${idx}`, {method: 'DELETE'});
        loadMemory();
    } catch (e) { alert('删除失败'); }
}

async function editMemory(idx) {
    const np = prompt('输入修改后的价格列表（逗号分隔）:');
    if (!np) return;
    try {
        await fetch(`/api/memory/edit/${idx}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prices: np})
        });
        loadMemory();
    } catch (e) { alert('修改失败'); }
}

async function updateWeights() {
    if (!confirm('确认更新权重？')) return;
    try {
        const res = await fetch('/api/weights/update', {method: 'POST'});
        const result = await res.json();
        if (res.ok) alert(`权重已更新！红色均价: ${result.red_mean.toLocaleString()}`);
    } catch (e) { alert('请求失败'); }
}

// ========== 置顶按钮（可拖动，限制范围，跟手） ==========
let isPinned = true;
let pinDragOffset = { x: 0, y: 0 };
let isDraggingPin = false;
let dragDistance = 0;
let mouseDownPos = { x: 0, y: 0 };
let pinFramePending = false;

async function togglePin() {
    const btn = document.getElementById('pin-btn');
    try {
        const response = await fetch('/api/toggle_on_top', {method: 'POST'});
        const result = await response.json();
        if (result.success) {
            isPinned = result.on_top;
            btn.classList.toggle('active', isPinned);
            btn.title = isPinned ? '取消置顶' : '窗口置顶';
        }
    } catch (e) {
        console.error('置顶切换失败:', e);
    }
}

function clampPosition(x, y, btn) {
    const btnWidth = btn.offsetWidth || 34;
    const btnHeight = btn.offsetHeight || 34;
    const margin = 4;
    
    const maxX = window.innerWidth - btnWidth - margin;
    const maxY = window.innerHeight - btnHeight - margin;
    
    return {
        x: Math.max(margin, Math.min(x, maxX)),
        y: Math.max(margin, Math.min(y, maxY))
    };
}

function initPinDrag() {
    const btn = document.getElementById('pin-btn');
    if (!btn) return;
    
    btn.addEventListener('mousedown', function(e) {
        isDraggingPin = true;
        dragDistance = 0;
        mouseDownPos.x = e.clientX;
        mouseDownPos.y = e.clientY;
        const rect = btn.getBoundingClientRect();
        pinDragOffset.x = e.clientX - rect.left;
        pinDragOffset.y = e.clientY - rect.top;
        e.preventDefault();
        e.stopPropagation();
    });
    
    document.addEventListener('mousemove', function(e) {
        if (!isDraggingPin) return;
        
        dragDistance = Math.max(
            Math.abs(e.clientX - mouseDownPos.x),
            Math.abs(e.clientY - mouseDownPos.y)
        );
        
        const btn = document.getElementById('pin-btn');
        if (!btn) return;
        
        if (pinFramePending) return;
        pinFramePending = true;
        
        requestAnimationFrame(() => {
            pinFramePending = false;
            const newX = e.clientX - pinDragOffset.x;
            const newY = e.clientY - pinDragOffset.y;
            const pos = clampPosition(newX, newY, btn);
            btn.style.left = pos.x + 'px';
            btn.style.top = pos.y + 'px';
            btn.style.right = 'auto';
            btn.style.bottom = 'auto';
        });
    });
    
    document.addEventListener('mouseup', function() {
        if (isDraggingPin && dragDistance < 5) {
            togglePin();
        }
        isDraggingPin = false;
    });
    
    // 窗口大小改变时，确保按钮在可视区域内
    window.addEventListener('resize', function() {
        const rect = btn.getBoundingClientRect();
        const pos = clampPosition(rect.left, rect.top, btn);
        btn.style.left = pos.x + 'px';
        btn.style.top = pos.y + 'px';
    });
}

document.addEventListener('DOMContentLoaded', function() {
    selectedGoldPrices = window.selectedGoldPrices || [];
    selectedRedPrices = window.selectedRedPrices || [];
    const knownGoldCountInput = document.getElementById('known_gold_count');
    if (knownGoldCountInput) {
        knownGoldCountInput.addEventListener('input', () => {
            window.ocrKnownGoldCountFromScreen = false;
        });
    }
    loadPriceOptions();
    renderSelectedPrices('gold');
    renderSelectedPrices('red');
    setEmptyResults();
    initPinDrag();
});