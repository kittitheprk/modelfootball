/**
 * Football Analytics Interactive Dashboard
 * Advanced Team & Player Comparison System
 */

// ============================================
// GLOBAL STATE MANAGEMENT
// ============================================
const state = {
    data: null,
    charts: {},
    filters: {
        leagues: ['all'],
        season: '2024-25',
        selectedTeams: [],
        selectedPlayers: [],
        positions: ['all'],
        minutesPlayed: 0,
        ageRange: { min: 16, max: 40 }
    },
    currentTab: 'teamDNA',
    currentPosition: 'MF'
};

// ============================================
// CHART CONFIGURATIONS
// ============================================
const chartColors = {
    primary: ['#667eea', '#f093fb', '#4facfe', '#fee140', '#fa709a', '#00f2fe'],
    gradients: [
        { start: '#667eea', end: '#764ba2' },
        { start: '#f093fb', end: '#f5576c' },
        { start: '#4facfe', end: '#00f2fe' }
    ]
};

Chart.defaults.color = '#b4b4c5';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 20;

// ============================================
// DATA LOADING & INITIALIZATION
// ============================================
async function loadData() {
    try {
        showLoading(true);
        const response = await fetch('data.json');
        state.data = await response.json();

        // Calculate Advanced Metrics
        calculateAdvancedMetrics();

        console.log('Data loaded:', {
            teams: state.data.teams.length,
            players: state.data.players.length,
            leagues: state.data.metadata.leagues
        });

        initializeFilters();
        initializeEventListeners();
        updateDashboard();
        showLoading(false);
    } catch (error) {
        console.error('Error loading data:', error);
        showLoading(false);
        alert('Error loading data. Please check console for details.');
    }
}

function calculateAdvancedMetrics() {
    state.data.teams.forEach(team => {
        const m = team.metrics;

        // 1. PPDA (Passes Per Defensive Action)
        // Formula: Opponent Passes allowed / Defensive Actions
        const defActions = (m.tackles || 0) + (m.interceptions || 0) + (m.fouls || 0);
        team.metrics.calc_PPDA = defActions > 0 ? (m.accurateOwnHalfPassesAgainst || 0) / defActions : 0;

        // 2. OPPDA (Opponent PPDA)
        // Formula: Our Passes / Opponent Defensive Actions
        const oppDefActions = (m.tacklesAgainst || 0) + (m.interceptionsAgainst || 0);
        team.metrics.calc_OPPDA = oppDefActions > 0 ? (m.accurateOwnHalfPasses || 0) / oppDefActions : 0;

        // 3. Field Tilt %
        // Formula: Final Third Passes / (Final Third Passes + Opp Final Third Passes)
        // Using OppositionHalfPasses as proxy if FinalThird not available or explicit
        const ourAttPasses = m.accurateOppositionHalfPasses || 0;
        const oppAttPasses = m.accurateOppositionHalfPassesAgainst || 0;
        const totalAttPasses = ourAttPasses + oppAttPasses;
        team.metrics.calc_FieldTilt_Pct = totalAttPasses > 0 ? (ourAttPasses / totalAttPasses) * 100 : 50;

        // 4. High Error Rate
        team.metrics.calc_HighError_Rate = (m.errorsLeadingToShot || 0) + (m.errorsLeadingToGoal || 0);

        // 5. Directness
        // Formula: Long Balls / Total Passes
        const totalPasses = m.totalPasses || 1;
        team.metrics.calc_Directness = (m.totalLongBalls || 0) / totalPasses;
        // Convert to percentage for chart if needed, but keeping as ratio for now

        // 6. Big Chance Diff
        team.metrics.calc_BigChance_Diff = (m.bigChances || 0) - (m.bigChancesAgainst || 0);
    });
}


function initializeFilters() {
    // Populate league filter
    const leagueFilter = document.getElementById('leagueFilter');
    state.data.metadata.leagues.forEach(league => {
        const option = document.createElement('option');
        option.value = league;
        option.textContent = league.replace('_', ' ');
        leagueFilter.appendChild(option);
    });

    // Populate initial Team Dropdown
    updateTeamDropdown();
    updatePlayerDropdown();

    updateHeaderStats();
}

function updateTeamDropdown() {
    const teamSelect = document.getElementById('teamSelect');
    teamSelect.innerHTML = '<option value="all">Select Team...</option>';

    // Filter teams based on selected leagues
    const activeLeagues = state.filters.leagues;
    const teams = state.data.teams.filter(t =>
        activeLeagues.includes('all') || activeLeagues.includes(t.league)
    );

    teams.sort((a, b) => a.name.localeCompare(b.name)).forEach(team => {
        const option = document.createElement('option');
        option.value = team.id;
        option.textContent = team.name;
        teamSelect.appendChild(option);
    });
}

function updatePlayerDropdown() {
    const playerSelect = document.getElementById('playerSelect');
    playerSelect.innerHTML = '<option value="all">Select Player...</option>';

    const selectedTeamIds = state.filters.selectedTeams;

    // If teams are selected, filter by team. If not, only show if user interacts or limit to top/league.
    // For performance, let's limit 

    let players = state.data.players;

    if (selectedTeamIds.length > 0) {
        // Get selected team names to filter players by squad
        const teams = state.data.teams.filter(t => selectedTeamIds.includes(t.id));
        const teamNames = teams.map(t => t.name);
        players = state.data.players.filter(p => teamNames.includes(p.squad));
    } else if (!state.filters.leagues.includes('all')) {
        // Filter by league if no specific team selected
        players = players.filter(p => state.filters.leagues.includes(p.league));
    } else {
        // Too many players? Limit to top 100 alpha or require selection
        playerSelect.innerHTML = '<option value="all">Select League or Team to load players...</option>';
        return;
    }

    players.sort((a, b) => a.name.localeCompare(b.name)).forEach(player => {
        const option = document.createElement('option');
        option.value = player.name; // ID is name for players currently
        option.textContent = `${player.name} (${player.position})`;
        playerSelect.appendChild(option);
    });
}

function updateHeaderStats() {
    const filtered = getFilteredData();
    document.getElementById('teamCount').textContent = filtered.teams.length;
    document.getElementById('playerCount').textContent = filtered.players.length;
    document.getElementById('leagueCount').textContent =
        new Set(filtered.teams.map(t => t.league)).size;
}

// ============================================
// EVENT LISTENERS
// ============================================
function initializeEventListeners() {
    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });

    // Core Filters
    document.getElementById('leagueFilter').addEventListener('change', (e) => {
        state.filters.leagues = Array.from(e.target.selectedOptions).map(o => o.value);
        if (state.filters.leagues.length === 0) state.filters.leagues = ['all'];

        updateTeamDropdown();
        updatePlayerDropdown();
        // Clear selected teams if they are not in the new league selection?
        // Ideally yes, but for now let's just update the available options
        updateDashboard();
    });

    // Team Filter (Linked)
    document.getElementById('teamSelect').addEventListener('change', (e) => {
        const teamId = parseFloat(e.target.value); // IDs are numbers in data
        if (!isNaN(teamId)) {
            addSelectedTeam(teamId);
            e.target.value = 'all'; // Reset dropdown
        }
    });

    // Player Filter (Linked)
    document.getElementById('playerSelect').addEventListener('change', (e) => {
        const playerName = e.target.value;
        if (playerName !== 'all') {
            addSelectedPlayer(playerName);
            e.target.value = 'all';
        }
    });

    // Other filters
    document.getElementById('positionFilter').addEventListener('change', handleFilterChange);
    document.getElementById('minutesFilter').addEventListener('input', handleMinutesChange);
    document.getElementById('ageMin').addEventListener('change', handleAgeChange);
    document.getElementById('ageMax').addEventListener('change', handleAgeChange);

    // Clear and Export
    document.getElementById('clearAllBtn').addEventListener('click', clearAllFilters);
    document.getElementById('exportBtn').addEventListener('click', exportData);

    // Metric Focus
    const metricFocus = document.getElementById('metricFocus');
    if (metricFocus) {
        metricFocus.addEventListener('change', () => {
            if (state.currentTab === 'teamDNA') {
                updateTeamDNATab();
            }
        });
    }

    // Position Selectors (Buttons)
    document.querySelectorAll('.pos-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // We need to verify we are actually in the right tab or context
            // but usually safe to update state
            document.querySelectorAll('.pos-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.currentPosition = btn.dataset.pos;

            // Only update view if looking at positional tab
            if (state.currentTab === 'positional') {
                updatePositionalTab();
            }
        });
    });

    // Similar Player
    const similarBtn = document.getElementById('similarPlayerBtn');
    if (similarBtn) similarBtn.addEventListener('click', findSimilarPlayers);

    // Sidebar
    document.getElementById('sidebarToggle').addEventListener('click', () => {
        document.getElementById('sidebar').classList.toggle('open');
    });
}

function addSelectedTeam(teamId) {
    if (state.filters.selectedTeams.includes(teamId)) return;
    state.filters.selectedTeams.push(teamId);

    // Render Team Tags
    renderSelectedTags('selectedTeams', state.filters.selectedTeams, (id) => {
        const t = state.data.teams.find(x => x.id === id);
        return t ? t.name : 'Unknown';
    }, (id) => {
        state.filters.selectedTeams = state.filters.selectedTeams.filter(x => x !== id);
        addSelectedTeam(null); // Recursively re-render
        updatePlayerDropdown();
        updateDashboard();
    });

    updatePlayerDropdown();
    updateDashboard();
}

function addSelectedPlayer(playerName) {
    if (!playerName) {
        // Just re-render
        renderSelectedTags('selectedPlayers', state.filters.selectedPlayers, name => name, (name) => {
            state.filters.selectedPlayers = state.filters.selectedPlayers.filter(x => x !== name);
            addSelectedPlayer(null); // Re-render
            updateDashboard();
        });
        return;
    }

    if (state.filters.selectedPlayers.includes(playerName)) return;
    state.filters.selectedPlayers.push(playerName);
    addSelectedPlayer(null);
    updateDashboard();
}

// Fixed Render Function
function renderSelectedTags(containerId, items, labelFn, removeFn) {
    const container = document.getElementById(containerId);
    container.innerHTML = '';
    items.forEach(item => {
        // Skip null/undefined
        if (item === null) return;

        const tag = document.createElement('div');
        tag.className = 'selected-item';
        tag.innerHTML = `<span>${labelFn(item)}</span><button class="remove-item">×</button>`;
        tag.querySelector('.remove-item').addEventListener('click', () => {
            removeFn(item);
        });
        container.appendChild(tag);
    });
}


function handleFilterChange() {
    const positionSelect = document.getElementById('positionFilter');
    state.filters.positions = Array.from(positionSelect.selectedOptions).map(o => o.value);
    if (state.filters.positions.length === 0) state.filters.positions = ['all'];
    updateDashboard();
}

function handleMinutesChange(e) {
    state.filters.minutesPlayed = parseInt(e.target.value);
    document.getElementById('minutesValue').textContent = state.filters.minutesPlayed + '+';
    updateDashboard();
}

function handleAgeChange() {
    const min = parseInt(document.getElementById('ageMin').value);
    const max = parseInt(document.getElementById('ageMax').value);
    state.filters.ageRange = { min, max };
    document.getElementById('ageValue').textContent = `${min}-${max}`;
    updateDashboard();
}

function clearAllFilters() {
    // Reset all filter values
    state.filters.leagues = ['all'];
    state.filters.selectedTeams = [];
    state.filters.selectedPlayers = [];
    state.filters.positions = ['all'];
    state.filters.minutesPlayed = 0;

    // Reset UI
    document.getElementById('leagueFilter').selectedIndex = 0;
    updateTeamDropdown();
    document.getElementById('teamSelect').value = 'all';
    document.getElementById('selectedTeams').innerHTML = '';

    document.getElementById('playerSelect').value = 'all';
    document.getElementById('playerSelect').innerHTML = '<option value="all">Select Team...</option>';
    document.getElementById('selectedPlayers').innerHTML = '';

    document.getElementById('positionFilter').selectedIndex = 0;
    document.getElementById('minutesFilter').value = 0;
    document.getElementById('minutesValue').textContent = '0+';

    updateDashboard();
}

// ============================================
// DATA FILTERING
// ============================================
function getFilteredData() {
    let teams = state.data.teams;
    let players = state.data.players;

    // Apply league filter
    if (!state.filters.leagues.includes('all')) {
        teams = teams.filter(t => state.filters.leagues.includes(t.league));
        players = players.filter(p => state.filters.leagues.includes(p.league));
    }

    // Apply position filter
    if (!state.filters.positions.includes('all')) {
        players = players.filter(p => {
            const pos = p.position.substring(0, 2);
            return state.filters.positions.includes(pos);
        });
    }

    // Apply minutes filter
    const minutesThreshold = state.filters.minutesPlayed / 90;
    players = players.filter(p => p.minutes90s >= minutesThreshold);

    return { teams, players };
}

// ============================================
// TAB SWITCHING
// ============================================
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === tabName);
    });

    const titles = {
        'teamDNA': 'Team DNA & Tactical Landscape',
        'matchAnalysis': 'Match Analysis & Styles',
        'teamComparison': 'Head-to-Head Team Comparison',
        'playerScouting': 'Player Scouting & Performance',
        'positional': 'Positional Deep Dive'
    };
    document.getElementById('pageTitle').textContent = titles[tabName] || 'Dashboard';

    state.currentTab = tabName;
    updateDashboard();
}

// ============================================
// DASHBOARD UPDATE
// ============================================
function updateDashboard() {
    updateHeaderStats();

    switch (state.currentTab) {
        case 'teamDNA':
            updateTeamDNATab();
            break;
        case 'matchAnalysis':
            updateMatchAnalysisTab();
            break;
        case 'teamComparison':
            updateTeamComparisonTab();
            break;
        case 'playerScouting':
            updatePlayerScoutingTab();
            break;
        case 'positional':
            updatePositionalTab();
            break;
    }
}

// ============================================
// TAB 1: TEAM DNA
// ============================================
function updateTeamDNATab() {
    const filtered = getFilteredData();
    const teams = filtered.teams;

    // Tactical Scatter Plot
    updateTacticalScatter(teams);

    // PPDA Bar Chart
    updatePPDABarChart(teams);

    // Field Tilt Chart
    updateFieldTiltChart(teams);
}

function updateTacticalScatter(teams) {
    const ctx = document.getElementById('tacticalScatterChart');
    if (!ctx) return;

    const metricFocus = document.getElementById('metricFocus').value;
    let xMetric, yMetric, xLabel, yLabel;

    switch (metricFocus) {
        case 'attacking':
            xMetric = 'accurateOppositionHalfPassesPercentage';
            yMetric = 'bigChances_per_90';
            xLabel = 'Opposition Half Passes % (Higher = More Attacking)';
            yLabel = 'Big Chances per 90 (Higher = More Creative)';
            break;
        case 'defensive':
            xMetric = 'interceptions_per_90';
            yMetric = 'tackles_per_90';
            xLabel = 'Interceptions per 90';
            yLabel = 'Tackles per 90';
            break;
        default:
            xMetric = 'averageBallPossession';
            yMetric = 'accurateOppositionHalfPassesPercentage';
            xLabel = 'Average Ball Possession %';
            yLabel = 'Opposition Half Passes %';
    }

    const data = teams.map(team => ({
        x: team.metrics[xMetric] || 0,
        y: team.metrics[yMetric] || 0,
        label: team.name,
        league: team.league
    })).filter(d => d.x !== 0 || d.y !== 0);

    destroyChart('tacticalScatter');

    state.charts.tacticalScatter = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Teams',
                data: data,
                backgroundColor: chartColors.primary[0],
                pointRadius: 6,
                pointHoverRadius: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const p = ctx.raw;
                            return `${p.label} (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`;
                        }
                    }
                },
                legend: { display: false }
            },
            scales: {
                x: { title: { display: true, text: xLabel, color: '#b4b4c5' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                y: { title: { display: true, text: yLabel, color: '#b4b4c5' }, grid: { color: 'rgba(255,255,255,0.1)' } }
            }
        }
    });
}

function updatePPDABarChart(teams) {
    const ctx = document.getElementById('ppdaBarChart');
    if (!ctx) return;
    const sorted = [...teams].sort((a, b) => b.metrics.tackles_per_90 - a.metrics.tackles_per_90).slice(0, 15);
    destroyChart('ppdaBar');
    state.charts.ppdaBar = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(t => t.name),
            datasets: [{
                label: 'Tackles/90',
                data: sorted.map(t => t.metrics.tackles_per_90),
                backgroundColor: createGradient(ctx, chartColors.gradients[0])
            }]
        },
        options: { indexAxis: 'y', maintainAspectRatio: false, responsive: true, plugins: { legend: { display: false } }, scales: { x: { grid: { color: 'rgba(255,255,255,0.1)' } }, y: { grid: { display: false } } } }
    });
}

function updateFieldTiltChart(teams) {
    const ctx = document.getElementById('fieldTiltChart');
    if (!ctx) return;
    const sorted = [...teams].sort((a, b) => b.metrics.averageBallPossession - a.metrics.averageBallPossession).slice(0, 15);
    destroyChart('fieldTilt');
    state.charts.fieldTilt = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(t => t.name),
            datasets: [{
                label: 'Possession %',
                data: sorted.map(t => t.metrics.averageBallPossession),
                backgroundColor: createGradient(ctx, chartColors.gradients[1])
            }]
        },
        options: { maintainAspectRatio: false, responsive: true, plugins: { legend: { display: false } }, scales: { y: { grid: { color: 'rgba(255,255,255,0.1)' } } } }
    });
}

// ============================================
// TAB 2: MATCH ANALYSIS (NEW)
// ============================================
function updateMatchAnalysisTab() {
    const filtered = getFilteredData();
    const teams = filtered.teams;

    updateControlDirectChart(teams);
    updateIntensityRiskChart(teams);
    updateTaleOfTheTapeChart(teams);
}

function updateControlDirectChart(teams) {
    const ctx = document.getElementById('controlDirectChart');
    if (!ctx) return;

    // x: Field Tilt, y: Directness, color: BigChanceDiff

    const data = teams.map(t => ({
        x: t.metrics.calc_FieldTilt_Pct || 50,
        y: (t.metrics.calc_Directness || 0) * 100, // Show as %
        label: t.name,
        bcd: t.metrics.calc_BigChance_Diff
    }));

    destroyChart('controlDirect');

    state.charts.controlDirect = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Teams',
                data: data.sort((a, b) => b.bcd - a.bcd), // Draw high bcd on top?
                pointBackgroundColor: (ctx) => {
                    const v = ctx.raw?.bcd || 0;
                    // Green for high positive, Red for negative
                    return v > 10 ? '#4ade80' : v < -5 ? '#f87171' : '#facc15';
                },
                pointRadius: 8,
                pointHoverRadius: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (c) => `${c.raw.label}: FT ${c.raw.x.toFixed(1)}%, Dir ${c.raw.y.toFixed(1)}%`
                    }
                },
                legend: { display: false }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Field Tilt % (Territorial Dominance)', color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                y: {
                    title: { display: true, text: 'Directness % (Lower = Short Passing)', color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    reverse: true
                }
            }
        }
    });
}

function updateIntensityRiskChart(teams) {
    const ctx = document.getElementById('intensityRiskChart');
    if (!ctx) return;

    // x: PPDA (Lower is better/more intense), y: High Error Rate
    const data = teams.map(t => ({
        x: t.metrics.calc_PPDA || 20,
        y: t.metrics.calc_HighError_Rate || 0,
        label: t.name,
        bcd: t.metrics.calc_BigChance_Diff
    }));

    destroyChart('intensityRisk');

    state.charts.intensityRisk = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Teams',
                data: data,
                pointBackgroundColor: (ctx) => {
                    const v = ctx.raw?.bcd || 0;
                    return v > 10 ? '#4ade80' : v < -5 ? '#f87171' : '#facc15';
                },
                pointRadius: 8,
                pointHoverRadius: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (c) => `${c.raw.label}: PPDA ${c.raw.x.toFixed(1)}, Errors ${c.raw.y}`
                    }
                },
                legend: { display: false }
            },
            scales: {
                x: {
                    title: { display: true, text: 'PPDA (Lower is Higher Intensity)', color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    reverse: true
                },
                y: {
                    title: { display: true, text: 'High Turnover Errors', color: '#aaa' },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                }
            }
        }
    });
}

function updateTaleOfTheTapeChart(teamsInView) {
    const ctx = document.getElementById('taleOfTheTapeChart');
    if (!ctx) return;

    const selectedIds = state.filters.selectedTeams;
    if (selectedIds.length !== 2) {
        destroyChart('taleOfTheTape');

        ctx.getContext('2d').clearRect(0, 0, ctx.width, ctx.height);
        // We could render text here if we wanted
        return;
    }

    const t1 = state.data.teams.find(t => t.id === selectedIds[0]);
    const t2 = state.data.teams.find(t => t.id === selectedIds[1]);

    if (!t1 || !t2) return;

    const labels = ['PPDA (Low=Good)', 'OPPDA (High=Good)', 'Field Tilt %', 'High Errors (Low=Good)', 'Directness %', 'Big Chance Diff'];
    const v1 = [
        t1.metrics.calc_PPDA,
        t1.metrics.calc_OPPDA,
        t1.metrics.calc_FieldTilt_Pct,
        t1.metrics.calc_HighError_Rate,
        t1.metrics.calc_Directness * 100,
        t1.metrics.calc_BigChance_Diff
    ];
    const v2 = [
        t2.metrics.calc_PPDA,
        t2.metrics.calc_OPPDA,
        t2.metrics.calc_FieldTilt_Pct,
        t2.metrics.calc_HighError_Rate,
        t2.metrics.calc_Directness * 100,
        t2.metrics.calc_BigChance_Diff
    ];

    destroyChart('taleOfTheTape');

    state.charts.taleOfTheTape = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: t1.name,
                    data: v1,
                    backgroundColor: 'rgba(255, 99, 132, 0.7)'
                },
                {
                    label: t2.name,
                    data: v2,
                    backgroundColor: 'rgba(54, 162, 235, 0.7)'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { grid: { color: '#333' } },
                x: { grid: { display: false } }
            }
        }
    });
}


// ============================================
// TAB 3: TEAM H2H (Team Comparison)
// ============================================
function updateTeamComparisonTab() {
    const selectedTeamIds = state.filters.selectedTeams;

    if (selectedTeamIds.length === 0) {
        document.getElementById('comparisonInfo').textContent = 'Select teams from the sidebar to compare';
        destroyChart('teamRadar');
        document.getElementById('teamComparisonTable').innerHTML = '<p style="text-align: center; color: #7a7a8c; padding: 40px;">No teams selected</p>';
        return;
    }

    const teams = state.data.teams.filter(t => selectedTeamIds.includes(t.id));
    document.getElementById('comparisonInfo').textContent = `Comparing ${teams.length} team${teams.length > 1 ? 's' : ''}`;

    updateTeamRadarChart(teams);
    updateTeamComparisonTable(teams);
}

function updateTeamRadarChart(teams) {
    const ctx = document.getElementById('teamRadarChart');
    if (!ctx) return;
    const radarMetrics = ['averageBallPossession', 'bigChances_per_90', 'tackles_per_90', 'interceptions_per_90', 'accuratePassesPercentage', 'goalConversion'];
    const datasets = teams.map((team, index) => ({
        label: team.name,
        data: radarMetrics.map(m => team.metrics[m] || 0),
        borderColor: chartColors.primary[index % chartColors.primary.length],
        backgroundColor: chartColors.primary[index % chartColors.primary.length] + '40',
        borderWidth: 3
    }));
    destroyChart('teamRadar');
    state.charts.teamRadar = new Chart(ctx, {
        type: 'radar',
        data: { labels: radarMetrics, datasets },
        options: { responsive: true, maintainAspectRatio: false, scales: { r: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.1)' }, pointLabels: { color: '#b4b4c5' }, ticks: { display: false } } } }
    });
}

function updateTeamComparisonTable(teams) {
    const container = document.getElementById('teamComparisonTable');
    const metricsToShow = Object.keys(teams[0].metrics).filter(m => !m.endsWith('_percentile') && !m.startsWith('calc_')).slice(0, 15);
    let html = '<table><thead><tr><th>Metric</th>' + teams.map(t => `<th>${t.name}</th>`).join('') + '</tr></thead><tbody>';

    // Add calc metrics first
    const calcMetrics = ['calc_PPDA', 'calc_FieldTilt_Pct', 'calc_Directness', 'calc_HighError_Rate'];
    calcMetrics.forEach(metric => {
        html += `<tr><td class="metric-name">${metric.replace('calc_', '')}</td>`;
        const values = teams.map(t => t.metrics[metric] || 0);
        values.forEach(v => { html += `<td class="metric-value">${v.toFixed(2)}</td>`; });
        html += '</tr>';
    });

    metricsToShow.forEach(metric => {
        html += `<tr><td class="metric-name">${metric}</td>`;
        const values = teams.map(t => t.metrics[metric] || 0);
        const max = Math.max(...values);
        values.forEach(v => { html += `<td class="${v === max && max > 0 ? 'metric-value metric-best' : 'metric-value'}">${v.toFixed(2)}</td>`; });
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

// ============================================
// TAB 4: PLAYER SCOUTING
// ============================================
function updatePlayerScoutingTab() {
    const filtered = getFilteredData();
    updateCreatorFinisherChart(filtered.players);
    updatePlayerRadarChart();
}

function updateCreatorFinisherChart(players) {
    const ctx = document.getElementById('creatorFinisherChart');
    if (!ctx) return;
    const playersWithData = players.filter(p => p.metrics['xAG'] && p.metrics['npxG']);
    const data = playersWithData.map(player => ({
        x: player.metrics['xAG']?.per90 || 0,
        y: player.metrics['npxG']?.per90 || 0,
        label: player.name,
        isSelected: state.filters.selectedPlayers.includes(player.name)
    }));
    const unselected = data.filter(d => !d.isSelected);
    const selected = data.filter(d => d.isSelected);

    destroyChart('creatorFinisher');
    state.charts.creatorFinisher = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [
                { label: 'All', data: unselected, backgroundColor: 'rgba(102, 126, 234, 0.3)', pointRadius: 4 },
                { label: 'Selected', data: selected, backgroundColor: chartColors.primary[0], pointRadius: 10 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { tooltip: { callbacks: { label: c => `${c.raw.label} (xAG: ${c.raw.x.toFixed(2)}, npxG: ${c.raw.y.toFixed(2)})` } }, legend: { display: false } }
        }
    });
}

function updatePlayerRadarChart() {
    const ctx = document.getElementById('playerRadarChart');
    if (!ctx) return;
    const selectedNames = state.filters.selectedPlayers;

    // Clear if no selection
    if (selectedNames.length === 0) {
        destroyChart('playerRadar');
        // Optional: show placeholder text
        return;
    }

    const players = state.data.players.filter(p => selectedNames.includes(p.name));

    // Expanded Metrics List for FBref style profile
    // Organized roughly by Attacking -> Possession -> Defending
    const metrics = [
        'Non_Penalty_Goals', 'npxG', 'Shots_Total',
        'Assists', 'xAG', 'Shot_Creating_Actions',
        'Passes_Attempted', 'Progressive_Passes', 'Successful_Take_Ons',
        'Touches_Att_Pen',
        'Tackles', 'Interceptions', 'Blocks', 'Aerials_Won'
    ];

    // FBref Palette
    const categoryColors = {
        attacking: 'rgba(255, 99, 132, 0.15)',   // Reddish
        possession: 'rgba(54, 162, 235, 0.15)',  // Blueish
        defending: 'rgba(75, 192, 192, 0.15)'    // Greenish
    };

    // Metric Categorization
    const metricCategories = {
        'Non_Penalty_Goals': 'attacking', 'npxG': 'attacking', 'Shots_Total': 'attacking',
        'Assists': 'attacking', 'xAG': 'attacking', 'Shot_Creating_Actions': 'attacking',
        'Passes_Attempted': 'possession', 'Progressive_Passes': 'possession',
        'Successful_Take_Ons': 'possession', 'Touches_Att_Pen': 'possession',
        'Tackles': 'defending', 'Interceptions': 'defending', 'Blocks': 'defending', 'Aerials_Won': 'defending'
    };

    // Custom Plugin to draw colored sectors
    const backgroundPlugin = {
        id: 'categoryBackgrounds',
        beforeDraw: (chart) => {
            const { ctx, scales: { r } } = chart;
            if (!r) return;

            const radius = r.drawingArea;
            // Use getDistanceFromCenterForValue to find the pixel distance for 100
            // Note: In Chart.js 4, r.getDistanceFromCenterForValue might vary, but usually r.getPointPosition(0, 100) works
            const outerPoint = r.getPointPosition(0, 100);
            const dx = outerPoint.x - r.xCenter;
            const dy = outerPoint.y - r.yCenter;
            const activityRadius = Math.sqrt(dx * dx + dy * dy);

            const totalMetrics = chart.data.labels.length;
            const centerX = r.xCenter;
            const centerY = r.yCenter;
            const anglePerSlice = (Math.PI * 2) / totalMetrics;
            const startAngle = -Math.PI / 2; // 12 o'clock

            ctx.save();
            chart.data.labels.forEach((label, i) => {
                const metricKey = metrics[i];
                const category = metricCategories[metricKey] || 'possession';

                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                const start = startAngle + (i * anglePerSlice);
                const end = start + anglePerSlice;
                ctx.arc(centerX, centerY, activityRadius, start, end);
                ctx.fillStyle = categoryColors[category];
                ctx.fill();
            });
            ctx.restore();
        }
    };

    const datasets = players.map((p, i) => {
        const color = chartColors.primary[i % chartColors.primary.length];
        return {
            label: p.name,
            // Prioritize positional percentile if available, else global
            data: metrics.map(m => p.metrics[m]?.pos_percentile ?? p.metrics[m]?.percentile ?? 0),
            borderColor: color,
            backgroundColor: 'transparent',
            fill: false,
            borderWidth: 3,
            pointBackgroundColor: color,
            pointRadius: 4,
            pointBorderColor: '#fff',
            pointBorderWidth: 1
        };
    });

    destroyChart('playerRadar');

    state.charts.playerRadar = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: metrics.map(m => m.replace(/_/g, ' ').replace('Non Penalty', 'NP').replace('Shot Creating', 'SCA').replace('Successful', '').trim()),
            datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    beginAtZero: true,
                    ticks: {
                        display: true,
                        stepSize: 20,
                        color: 'rgba(255,255,255,0.4)',
                        backdropColor: 'transparent',
                        font: { size: 9 }
                    },
                    grid: { color: 'rgba(255,255,255,0.2)', circular: true, lineWidth: 1 },
                    pointLabels: {
                        font: { size: 12, weight: 'bold', family: "'Inter', sans-serif" },
                        color: (context) => {
                            const index = context.index;
                            const key = metrics[index];
                            const cat = metricCategories[key];
                            if (cat === 'attacking') return '#ff6384';
                            if (cat === 'defending') return '#4bc0c0';
                            return '#36a2eb'; // possession
                        },
                        padding: 10
                    },
                    angleLines: {
                        display: true,
                        color: 'rgba(255,255,255,0.4)',
                        lineWidth: 2
                    }
                }
            },
            plugins: {
                legend: { position: 'top', labels: { color: '#fff', usePointStyle: true, font: { size: 14 } } },
                tooltip: {
                    callbacks: { label: c => `${c.dataset.label}: ${c.raw.toFixed(1)}th Percentile` }
                }
            }
        },
        plugins: [backgroundPlugin]
    });
}

// ============================================
// TAB 5: POSITIONAL
// ============================================
function updatePositionalTab() {
    const filtered = getFilteredData();
    const positionPlayers = filtered.players.filter(p => p.position.includes(state.currentPosition));
    updatePositionalChart(positionPlayers);
    updateTopPerformers(positionPlayers);
    updateDistributionChart(positionPlayers);
}

function updatePositionalChart(players) {
    const ctx = document.getElementById('positionalChart');
    if (!ctx) return;
    let xMetric = 'Progressive_Passes', yMetric = 'Shot_Creating_Actions';
    if (state.currentPosition === 'FW') { xMetric = 'npxG'; yMetric = 'Shots_Total'; }
    if (state.currentPosition === 'DF') { xMetric = 'Tackles'; yMetric = 'Interceptions'; }

    const data = players.map(p => ({
        x: p.metrics[xMetric]?.per90 || 0,
        y: p.metrics[yMetric]?.per90 || 0,
        r: Math.min((p.minutes90s || 1) * 2, 20),
        label: p.name
    })).slice(0, 100);

    destroyChart('positional');
    state.charts.positional = new Chart(ctx, {
        type: 'bubble',
        data: { datasets: [{ label: state.currentPosition, data: data, backgroundColor: chartColors.primary[2] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
}

function updateTopPerformers(players) {
    const container = document.getElementById('topPerformers');
    container.innerHTML = '';
    const relevantMetric = state.currentPosition === 'FW' ? 'Non_Penalty_Goals' : 'Progressive_Passes';
    const top5 = [...players].sort((a, b) => (b.metrics[relevantMetric]?.per90 || 0) - (a.metrics[relevantMetric]?.per90 || 0)).slice(0, 5);

    top5.forEach((p, i) => {
        const div = document.createElement('div');
        div.className = 'player-card-mini';
        div.innerHTML = `<div class="rank">#${i + 1}</div>
                         <div class="info"><strong>${p.name}</strong><br>${p.squad}</div>
                         <div class="stat">${(p.metrics[relevantMetric]?.per90 || 0).toFixed(2)}</div>`;
        container.appendChild(div);
    });
}

function updateDistributionChart(players) {
    const ctx = document.getElementById('distributionChart');
    if (!ctx) return;
    // Simple placeholder distribution
    destroyChart('distribution');
}

// ============================================
// HELPERS
// ============================================
function createGradient(ctx, colors) {
    if (!ctx || !ctx.canvas || !ctx.canvas.parentNode) {
        return colors.start;
    }

    try {
        const chartArea = ctx.canvas.parentNode.getBoundingClientRect();
        if (!chartArea || chartArea.width === 0) {
            return colors.start;
        }

        const gradient = ctx.createLinearGradient(0, 0, chartArea.width, 0);
        gradient.addColorStop(0, colors.start);
        gradient.addColorStop(1, colors.end);
        return gradient;
    } catch (e) {
        console.warn('Gradient creation failed, using solid color:', e);
        return colors.start;
    }
}

function destroyChart(name) {
    if (state.charts[name]) {
        state.charts[name].destroy();
        state.charts[name] = null;
    }
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = show ? 'flex' : 'none';
}

function exportData() {
    const filtered = getFilteredData();
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(filtered, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "football_data_export.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

function findSimilarPlayers() {
    alert('Feature coming soon in v2.1!');
}

// Start
document.addEventListener('DOMContentLoaded', loadData);
