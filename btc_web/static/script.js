/**
 * BTC Dashboard Frontend Script
 * 获取 API 数据并动态更新页面
 */

// 自动刷新间隔（毫秒）
const REFRESH_INTERVAL = 5 * 60 * 1000; // 5分钟

// 页面加载时获取数据
document.addEventListener('DOMContentLoaded', () => {
    fetchDashboardData();

    // 设置自动刷新
    setInterval(fetchDashboardData, REFRESH_INTERVAL);
});

// 刷新按钮点击事件
document.getElementById('refreshBtn')?.addEventListener('click', () => {
    fetchDashboardData();
});

/**
 * 获取仪表盘数据
 */
async function fetchDashboardData() {
    const refreshBtn = document.getElementById('refreshBtn');
    const mainContent = document.getElementById('mainContent');
    const loadingEl = document.getElementById('loading');

    // 显示加载状态
    if (refreshBtn) {
        refreshBtn.classList.add('spinning');
    }

    try {
        const response = await fetch('/api/dashboard');
        const data = await response.json();

        if (data.success) {
            renderDashboard(data);
            loadingEl.style.display = 'none';
            mainContent.style.display = 'block';
        } else {
            showError(data.error || '获取数据失败');
        }
    } catch (error) {
        console.error('Error fetching dashboard data:', error);
        showError('无法连接到服务器');
    } finally {
        if (refreshBtn) {
            refreshBtn.classList.remove('spinning');
        }
    }
}

/**
 * 渲染仪表盘
 */
function renderDashboard(data) {
    // 更新时间戳
    document.getElementById('timestamp').textContent = `更新时间: ${data.timestamp}`;

    // 更新价格 (safely check if element exists)
    const btcPriceEl = document.getElementById('btcPrice');
    if (btcPriceEl) {
        btcPriceEl.innerHTML = `<span class="currency">$</span>${formatNumber(data.btc_price)}`;
    }

    // 更新顶部摘要栏
    updateTopSummaryBar(data.btc_price, data.indicators);

    // 更新仪表盘指针
    updateGauge(data.total_score);

    // 更新评分
    document.getElementById('scoreValue').textContent = data.total_score.toFixed(2);

    // 更新建议
    const recommendationEl = document.getElementById('recommendation');
    recommendationEl.textContent = data.recommendation;
    recommendationEl.className = 'recommendation ' + getScoreColor(data.total_score);

    // 渲染指标
    renderIndicators(data.indicators);

    // 渲染指标总览表格
    renderSummaryTable(data.indicators);
}

/**
 * 更新顶部摘要栏
 */
function updateTopSummaryBar(btcPrice, indicators) {
    // 价格
    const priceEl = document.getElementById('summaryPrice');
    if (priceEl) {
        priceEl.textContent = '$' + btcPrice.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
    }

    // 价格趋势
    const changeEl = document.getElementById('summaryChange');
    if (changeEl && indicators['MACD']) {
        const macd = indicators['MACD'];
        if (macd.score > 0) {
            changeEl.textContent = '▲ 趋势向上';
            changeEl.className = 'change positive';
        } else if (macd.score < 0) {
            changeEl.textContent = '▼ 趋势向下';
            changeEl.className = 'change negative';
        } else {
            changeEl.textContent = '— 震荡';
            changeEl.className = 'change neutral';
        }
    }

    // 全网算力
    const hashrateEl = document.getElementById('summaryHashrate');
    if (hashrateEl && indicators['全网算力']) {
        const val = indicators['全网算力'].value;
        if (!isNaN(val)) {
            hashrateEl.textContent = val.toFixed(1) + ' EH/s';
        }
    }

    // Ahr999
    const ahr999El = document.getElementById('summaryAhr999');
    if (ahr999El && indicators['Ahr999']) {
        const val = indicators['Ahr999'].value;
        if (!isNaN(val)) {
            ahr999El.textContent = val.toFixed(2);
            ahr999El.style.color = val < 0.45 ? '#00ff88' : (val < 1.2 ? '#ffcc00' : '#ff4466');
        }
    }

    // 恐惧贪婪
    const fgEl = document.getElementById('summaryFearGreed');
    if (fgEl && indicators['恐惧贪婪指数']) {
        const val = indicators['恐惧贪婪指数'].value;
        if (!isNaN(val)) {
            fgEl.textContent = val.toFixed(0);
            fgEl.style.color = val < 25 ? '#00ff88' : (val > 75 ? '#ff4466' : '#ffcc00');
        }
    }

    // 减半倒计时
    const halvingEl = document.getElementById('summaryHalving');
    if (halvingEl && indicators['减半周期']) {
        const status = indicators['减半周期'].status;
        const match = status.match(/(\d+)\s*天/);
        if (match) {
            halvingEl.textContent = match[1] + '天';
        } else {
            halvingEl.textContent = Math.round(indicators['减半周期'].value) + '月';
        }
    }

    // 均衡价格
    const balancedEl = document.getElementById('summaryBalanced');
    if (balancedEl && indicators['均衡价格']) {
        const val = indicators['均衡价格'].value;
        if (!isNaN(val)) {
            balancedEl.textContent = '$' + val.toLocaleString(undefined, {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0
            });
        }
    }
}

/**
 * 渲染指标总览表格
 */
function renderSummaryTable(indicators) {
    console.log('renderSummaryTable called with:', indicators);
    const tbody = document.getElementById('summaryTableBody');
    console.log('tbody element:', tbody);
    if (!tbody) {
        console.error('summaryTableBody not found!');
        return;
    }

    tbody.innerHTML = '';

    // 定义指标排序（按优先级）
    const priorityOrder = ['P0', 'P1', 'P2'];

    // 将指标转换为数组并排序
    const sortedIndicators = Object.entries(indicators)
        .sort((a, b) => {
            const pA = priorityOrder.indexOf(a[1].priority || 'P2');
            const pB = priorityOrder.indexOf(b[1].priority || 'P2');
            return pA - pB;
        });

    for (const [name, indicator] of sortedIndicators) {
        const row = document.createElement('tr');

        // 获取结论和样式
        const conclusion = getConclusion(indicator);
        const conclusionClass = getConclusionClass(indicator);

        // 格式化数值
        let valueDisplay = '--';
        if (indicator.value !== null && !isNaN(indicator.value)) {
            if (indicator.value > 1000000000) {
                valueDisplay = `$${(indicator.value / 1e9).toFixed(1)}B`;
            } else if (indicator.value > 1000000) {
                valueDisplay = `$${(indicator.value / 1e6).toFixed(1)}M`;
            } else if (indicator.value > 100) {
                valueDisplay = `$${formatNumber(indicator.value)}`;
            } else {
                valueDisplay = indicator.value.toFixed(2);
            }
        }

        row.innerHTML = `
            <td>${indicator.name || name}</td>
            <td>${valueDisplay}</td>
            <td><span class="conclusion-badge ${conclusionClass}">${conclusion}</span></td>
        `;

        tbody.appendChild(row);
    }
}

/**
 * 根据指标获取结论文字
 */
function getConclusion(indicator) {
    const score = indicator.score;
    const color = indicator.color;

    // 根据 score 或 color 判断
    if (score >= 0.8) return '强烈看多';
    if (score >= 0.5) return '偏多';
    if (score >= 0.2) return '略偏多';
    if (score > -0.2) return '中立';
    if (score > -0.5) return '略偏空';
    if (score > -0.8) return '偏空';
    if (score <= -0.8) return '强烈看空';

    // 根据颜色 fallback
    if (color === '🟢') return '偏多';
    if (color === '🟡') return '中立';
    if (color === '🔴') return '偏空';
    if (color === '⚪') return '参考';

    return '中立';
}

/**
 * 根据指标获取结论样式类名
 */
function getConclusionClass(indicator) {
    const score = indicator.score;

    if (score >= 0.8) return 'strong-bullish';
    if (score >= 0.3) return 'bullish';
    if (score > -0.3) return 'neutral';
    if (score > -0.8) return 'bearish';
    if (score <= -0.8) return 'strong-bearish';

    // Fallback by color
    const color = indicator.color;
    if (color === '🟢') return 'bullish';
    if (color === '🟡') return 'neutral';
    if (color === '🔴') return 'bearish';

    return 'info';
}

/**
 * 更新仪表盘指针
 */
function updateGauge(score) {
    const needle = document.getElementById('gaugeNeedle');
    // score 范围是 -1 到 +1，映射到 -90 到 +90 度
    const angle = score * 90;
    needle.style.transform = `translateX(-50%) rotate(${angle}deg)`;
}

/**
 * 渲染指标卡片
 */
function renderIndicators(indicators) {
    const longTermContainer = document.getElementById('longTermIndicators');
    const shortTermContainer = document.getElementById('shortTermIndicators');
    const auxContainer = document.getElementById('auxIndicators');

    if (longTermContainer) longTermContainer.innerHTML = '';
    if (shortTermContainer) shortTermContainer.innerHTML = '';
    if (auxContainer) auxContainer.innerHTML = '';

    for (const [name, indicator] of Object.entries(indicators)) {
        const card = createIndicatorCard(indicator);

        if (indicator.priority === 'P0') {
            if (longTermContainer) longTermContainer.appendChild(card);
        } else if (indicator.priority === 'P1') {
            if (shortTermContainer) shortTermContainer.appendChild(card);
        } else if (auxContainer) {
            auxContainer.appendChild(card);
        }
    }
}

/**
 * 创建指标卡片（带迷你图表）
 */
function createIndicatorCard(indicator) {
    const card = document.createElement('div');
    card.className = `indicator-card ${getIndicatorColorClass(indicator.color)}`;

    // 生成唯一的 canvas ID
    const chartId = `chart-${indicator.name.replace(/\s+/g, '-')}`;

    // 支持图表的指标列表
    const chartableIndicators = ['Ahr999', '恐惧贪婪指数', '资金费率', '多空比', 'Pi Cycle Top'];
    const hasChart = chartableIndicators.includes(indicator.name);

    // 构建HTML
    let html = `
        <div class="indicator-header">
            <span class="indicator-name">${indicator.name}</span>
            <span class="indicator-priority ${indicator.priority}">${indicator.priority}</span>
        </div>
        <div class="indicator-status">
            <span class="status-icon">${indicator.color}</span>
            <span>${indicator.status}</span>
        </div>
        ${hasChart ? `<div class="indicator-chart"><canvas id="${chartId}" height="60"></canvas></div>` : ''}
    `;

    // 添加说明部分的容器 (如果有定义)
    if (indicator.description || indicator.method) {
        html += `
            <div class="indicator-details-toggle" onclick="toggleDetails(this)">
                <span>ℹ️ 指标说明</span>
                <span class="arrow">▼</span>
            </div>
            <div class="indicator-details" style="display: none;">
                ${indicator.description ? `<div class="detail-item"><strong>定义:</strong> ${indicator.description}</div>` : ''}
                ${indicator.method ? `<div class="detail-item"><strong>计算:</strong> ${indicator.method}</div>` : ''}
            </div>
        `;
    }

    card.innerHTML = html;

    // 如果由外部链接，添加点击事件和样式 (点击卡片头部跳转)
    if (indicator.url) {
        const header = card.querySelector('.indicator-header');
        header.classList.add('clickable');
        header.onclick = (e) => {
            e.stopPropagation();
            window.open(indicator.url, '_blank');
        };
        header.title = "点击查看原始图表";

        // 在名字旁添加链接图标
        const nameEl = card.querySelector('.indicator-name');
        if (nameEl) {
            nameEl.innerHTML += ' <span style="font-size: 0.8em; color: #888;">↗</span>';
        }
    }

    // 延迟加载图表
    if (hasChart) {
        setTimeout(() => fetchAndRenderChart(indicator.name, chartId), 100);
    }

    return card;
}

/**
 * 获取历史数据并渲染图表
 */
async function fetchAndRenderChart(indicatorName, canvasId) {
    try {
        const response = await fetch(`/api/history/${encodeURIComponent(indicatorName)}?days=30`);
        const data = await response.json();

        if (!data.success || !data.dates || data.dates.length === 0) {
            return; // 无数据则不显示图表
        }

        renderMiniChart(canvasId, data);
    } catch (error) {
        console.log(`Chart for ${indicatorName} unavailable:`, error);
    }
}

/**
 * 渲染迷你图表
 */
function renderMiniChart(canvasId, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    // 准备阈值线
    const annotations = [];
    if (data.thresholds) {
        Object.values(data.thresholds).forEach(threshold => {
            annotations.push({
                type: 'line',
                yMin: threshold.value,
                yMax: threshold.value,
                borderColor: threshold.color,
                borderWidth: 1,
                borderDash: [3, 3],
            });
        });
    }

    // 简化日期标签
    const labels = data.dates.map((d, i) => {
        if (i === 0 || i === data.dates.length - 1) {
            return d.slice(5); // MM-DD
        }
        return '';
    });

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                data: data.values,
                borderColor: '#f7931a',
                backgroundColor: 'rgba(247, 147, 26, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                        title: (items) => data.dates[items[0].dataIndex],
                        label: (item) => `${data.indicator}: ${item.raw}`
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: {
                        color: '#666',
                        font: { size: 9 },
                        maxRotation: 0
                    },
                    grid: { display: false }
                },
                y: {
                    display: false,
                    grid: { display: false }
                }
            },
            interaction: {
                mode: 'index',
                intersect: false
            }
        }
    });

    // 手动绘制阈值线（Chart.js 4.x 需要插件，这里简化处理）
    drawThresholdLines(canvas, ctx, data);
}

/**
 * 切换指标说明显示/隐藏
 */
function toggleDetails(element) {
    const details = element.nextElementSibling;
    const arrow = element.querySelector('.arrow');

    if (details.style.display === 'none') {
        details.style.display = 'block';
        arrow.textContent = '▲';
        element.classList.add('active');
    } else {
        details.style.display = 'none';
        arrow.textContent = '▼';
        element.classList.remove('active');
    }
}

/**
 * 绘制阈值参考线
 */
function drawThresholdLines(canvas, ctx, data) {
    if (!data.thresholds || !data.values || data.values.length === 0) return;

    const minVal = Math.min(...data.values);
    const maxVal = Math.max(...data.values);
    const range = maxVal - minVal || 1;

    // 画布尺寸
    const chartArea = {
        left: 0,
        right: canvas.width,
        top: 10,
        bottom: canvas.height - 15
    };
    const height = chartArea.bottom - chartArea.top;

    Object.values(data.thresholds).forEach(threshold => {
        if (threshold.value >= minVal && threshold.value <= maxVal) {
            const y = chartArea.bottom - ((threshold.value - minVal) / range) * height;

            ctx.beginPath();
            ctx.setLineDash([3, 3]);
            ctx.strokeStyle = threshold.color;
            ctx.lineWidth = 1;
            ctx.moveTo(chartArea.left, y);
            ctx.lineTo(chartArea.right, y);
            ctx.stroke();
        }
    });
}

/**
 * 获取指标颜色类名
 */
function getIndicatorColorClass(color) {
    switch (color) {
        case '🟢': return 'green';
        case '🟡': return 'yellow';
        case '🔴': return 'red';
        default: return 'neutral';
    }
}

/**
 * 获取评分颜色
 */
function getScoreColor(score) {
    if (score >= 0.5) return 'green';
    if (score >= -0.3) return 'yellow';
    return 'red';
}

/**
 * 格式化数字
 */
function formatNumber(num) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

/**
 * 显示错误信息
 */
function showError(message) {
    const mainContent = document.getElementById('mainContent');
    const loadingEl = document.getElementById('loading');

    loadingEl.innerHTML = `
        <div class="error">
            <h2>❌ 错误</h2>
            <p>${message}</p>
            <p style="margin-top: 20px; color: var(--text-muted);">请点击右下角按钮重试</p>
        </div>
    `;
}

/**
 * 获取资讯数据
 */
async function fetchNewsData() {
    console.log('Fetching news data...');
    try {
        const response = await fetch('/api/news');
        const data = await response.json();

        if (data.success) {
            // 渲染资讯
            if (data.news && data.news.length > 0) {
                renderCryptoNews(data.news);
            }
            // 渲染鲸鱼动态
            if (data.whales && data.whales.length > 0) {
                renderWhaleActivity(data.whales);
            }
            // 渲染宏观经济日历
            if (data.calendar && data.calendar.length > 0) {
                renderMacroCalendar(data.calendar);
            }
            console.log('News data loaded successfully');
        } else {
            console.error('News API error:', data.error);
        }
    } catch (error) {
        console.error('Failed to fetch news:', error);
    }
}

/**
 * 渲染 BTC 资讯
 */
function renderCryptoNews(news) {
    const container = document.getElementById('cryptoNews');
    if (!container) return;

    container.innerHTML = news.map(item => `
        <div class="news-item" style="margin-bottom: 12px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px;">
            <a href="${item.url}" target="_blank" style="color: #f79322; text-decoration: none; font-weight: 500;">
                ${item.icon || '📰'} ${item.title}
            </a>
            <div style="margin-top: 6px; font-size: 0.85rem; color: #888;">
                ${item.summary || ''}
            </div>
            <div style="margin-top: 4px; font-size: 0.75rem; color: #666;">
                ${item.source} · ${item.time}
            </div>
        </div>
    `).join('');
}

/**
 * 渲染鲸鱼动态
 */
function renderWhaleActivity(whales) {
    const container = document.getElementById('whaleActivity');
    if (!container) return;

    container.innerHTML = whales.map(item => {
        // 特殊处理 "链接" 类型
        if (item.type === '链接') {
            return `
            <a href="${item.url}" target="_blank" class="whale-item" style="display: block; text-decoration: none; margin-bottom: 8px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 6px; font-size: 0.9rem; text-align: center; color: #f79322; font-weight: 500;">
                ${item.icon || '🔗'} ${item.amount || '查看更多'}
            </a>
            `;
        }

        return `
        <a href="${item.url}" target="_blank" class="whale-item" style="display: block; text-decoration: none; margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.02); border-radius: 6px; font-size: 0.9rem; transition: background 0.2s;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: ${item.type.includes('流入') || item.type.includes('巨鲸') ? '#00ff88' : '#ff4466'}; display: flex; align-items: center; gap: 4px;">
                    ${item.icon || ''} ${item.type || '交易'}
                </span>
                <span style="color: #fff; font-weight: 500;">
                    ${item.amount}
                </span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 4px;">
                <span style="color: #666; font-size: 0.75rem;">
                    ${item.time}
                </span>
                <span style="color: #888; font-size: 0.8rem;">
                    ≈ ${item.value_usd}
                </span>
            </div>
        </a>
    `}).join('');
}


/**
 * 渲染宏观经济日历
 */
function renderMacroCalendar(events) {
    const container = document.getElementById('macroCalendar');
    if (!container) return;

    // 影响程度颜色映射
    const impactColor = {
        '高': '#ff4466',
        '中': '#f79322',
        '低': '#888'
    };

    container.innerHTML = events.map(item => {
        // 特殊处理 "链接" 类型
        if (item.type === '链接') {
            return `
            <a href="${item.url}" target="_blank" class="calendar-item" style="display: block; text-decoration: none; margin-bottom: 10px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; text-align: center; color: #f79322;">
                ${item.event}
            </a>
            `;
        }

        const impact = item.impact || '';
        const color = impactColor[impact] || '#888';
        const hasActual = item.has_actual;
        const isPast = item.is_past;
        const eventStatus = item.event_status || '';
        const actual = item.actual || '';
        const forecast = item.forecast || '';
        const previous = item.previous || '';

        // 状态徽章样式
        let statusBadge = '';
        if (eventStatus === '已公布') {
            statusBadge = `<span style="font-size: 0.65rem; padding: 1px 5px; border-radius: 3px; background: ${hasActual ? '#00c85322' : '#8884'}; color: ${hasActual ? '#00c853' : '#aaa'}; white-space: nowrap; margin-left: 6px; border: 1px solid ${hasActual ? '#00c85344' : '#8882'};">✓ 已公布</span>`;
        } else if (eventStatus === '待公布') {
            statusBadge = `<span style="font-size: 0.65rem; padding: 1px 5px; border-radius: 3px; background: #f7932211; color: #f79322; white-space: nowrap; margin-left: 6px; border: 1px solid #f7932233;">⏳ 待公布</span>`;
        }

        // 构建数据值行
        let dataRows = '';
        if (hasActual && actual) {
            // 有实际公布值 - 醒目显示
            dataRows += `<div style="margin-top: 5px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">`;
            dataRows += `<span style="font-size: 0.82rem; color: #00e676; font-weight: 600; background: #00e67615; padding: 1px 6px; border-radius: 4px;">📌 公布: ${actual}</span>`;
            if (forecast) {
                dataRows += `<span style="font-size: 0.75rem; color: #aaa;">预期: ${forecast}</span>`;
            }
            if (previous) {
                dataRows += `<span style="font-size: 0.75rem; color: #888;">前值: ${previous}</span>`;
            }
            dataRows += `</div>`;
        } else if (isPast) {
            // 已过去但没有actual - 显示预期和前值
            dataRows += `<div style="margin-top: 5px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">`;
            if (forecast) {
                dataRows += `<span style="font-size: 0.75rem; color: #ccc;">预期: ${forecast}</span>`;
            }
            if (previous) {
                dataRows += `<span style="font-size: 0.75rem; color: #888;">前值: ${previous}</span>`;
            }
            dataRows += `</div>`;
        } else {
            // 未来事件 - 显示预期和前值
            dataRows += `<div style="margin-top: 5px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">`;
            if (forecast) {
                dataRows += `<span style="font-size: 0.75rem; color: #ccc;">预期: ${forecast}</span>`;
            }
            if (previous) {
                dataRows += `<span style="font-size: 0.75rem; color: #888;">前值: ${previous}</span>`;
            }
            dataRows += `</div>`;
        }

        // 整体透明度：已公布事件稍暗
        const opacity = isPast && !hasActual ? '0.75' : '1';

        return `
        <div class="calendar-item" style="margin-bottom: 8px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 3px solid ${color}; opacity: ${opacity};">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="color: #e0e0e0; font-weight: 500; font-size: 0.9rem; flex: 1; display: flex; align-items: center; flex-wrap: wrap;">
                    ${item.event || item.title || '未知事件'}
                    ${statusBadge}
                </div>
                <span style="font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; background: ${color}22; color: ${color}; white-space: nowrap; margin-left: 8px;">
                    ${impact}
                </span>
            </div>
            <div style="margin-top: 4px; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 0.8rem; color: #888;">
                    📆 ${item.date || ''}
                </span>
            </div>
            ${dataRows}
        </div>
    `}).join('');
}

/**
 * 渲染加密日历
 */
function renderCryptoCalendar(events) {
    const container = document.getElementById('cryptoCalendar');
    if (!container) return;

    container.innerHTML = events.map(item => `
        <div class="calendar-item" style="margin-bottom: 10px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px;">
            <div style="color: #f79322; font-weight: 500;">
                ${item.icon || '📅'} ${item.event || item.title || '未知事件'}
                ${item.source ? `<span style="font-size: 0.7rem; color: #666; margin-left: 8px;">[${item.source}]</span>` : ''}
            </div>
            <div style="margin-top: 4px; font-size: 0.85rem; color: #aaa;">
                ${item.status || item.description || ''}
            </div>
            <div style="margin-top: 4px; font-size: 0.75rem; color: #666;">
                ${item.date || ''} ${item.type ? '· ' + item.type : ''} ${item.impact ? '· 影响: ' + item.impact : ''}
            </div>
        </div>
    `).join('');
}

// 页面加载后获取资讯数据
document.addEventListener('DOMContentLoaded', function () {
    // 延迟获取资讯，优先加载主要指标
    setTimeout(fetchNewsData, 3000);
});
