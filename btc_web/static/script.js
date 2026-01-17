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

    // 更新价格
    document.getElementById('btcPrice').innerHTML =
        `<span class="currency">$</span>${formatNumber(data.btc_price)}`;

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
    const p0Container = document.getElementById('p0Indicators');
    const p1Container = document.getElementById('p1Indicators');
    const p2Container = document.getElementById('p2Indicators');

    p0Container.innerHTML = '';
    p1Container.innerHTML = '';
    if (p2Container) p2Container.innerHTML = '';

    for (const [name, indicator] of Object.entries(indicators)) {
        const card = createIndicatorCard(indicator);

        if (indicator.priority === 'P0') {
            p0Container.appendChild(card);
        } else if (indicator.priority === 'P1') {
            p1Container.appendChild(card);
        } else if (p2Container) {
            p2Container.appendChild(card);
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

    card.innerHTML = `
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

    // 如果由外部链接，添加点击事件和样式
    if (indicator.url) {
        card.classList.add('clickable');
        card.onclick = () => window.open(indicator.url, '_blank');

        // 在状态中添加外部链接图标
        const statusEl = card.querySelector('.indicator-status span:last-child');
        if (statusEl) {
            statusEl.innerHTML += ' <span style="font-size: 0.8em;">↗</span>';
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

