# Football Analytics Interactive Dashboard v2.0

## 📊 Overview

Advanced web application for analyzing football team and player statistics with interactive filtering and comparison capabilities. Built with vanilla JavaScript, Chart.js, and premium modern UI design.

## ✨ Features

### 🎯 Core Filters (Sidebar)
- **League Selector**: Multi-select dropdown for league filtering
- **Season Selector**: Choose analysis season (currently 2024/25)

### ⚔️ Comparison Engine
- **Team Comparison**: Compare up to 3 teams simultaneously
- **Player Comparison**: Compare up to 3 players with autocomplete search
- Real-time filtering and highlighting

### 🔧 Advanced Filters
- **Position Filter**: Filter by FW, MF, DF, GK
- **Minutes Played Slider**: Filter out low-playing-time players (0-3000 mins)
- **Age Range**: Target specific age groups for scouting

### 📈 Four Analysis Tabs

#### Tab 1: Team DNA & Tactical Landscape
- **Tactical Scatter Plot**: Visualize team playing style (Field Tilt vs Directness vs PPDA)
- **Metric Focus Selector**: Switch between attacking, defensive, or balanced views
- **PPDA Ranking**: Top 15 teams by pressing intensity
- **Field Tilt Chart**: Top 15 teams by attacking dominance

#### Tab 2: Head-to-Head Team Comparison
- **Radar Chart**: 6-metric comparison overlay (2-3 teams)
- **Detailed Metrics Table**: Raw data comparison with best value highlighting
- Automatically adapts to number of selected teams

#### Tab 3: Player Scouting & Performance
- **Creator vs Finisher Matrix**: Scatter plot of xAG vs npxG per 90
  - Highlights selected players in color
  - Shows all league players in background for context
- **Player Profile Radar**: Percentile-based comparison (6 key metrics)
- **Similar Player Finder**: AI-powered similarity search

#### Tab 4: Positional Deep Dive
- **Dynamic Bubble Chart**: Changes metrics based on selected position
  - GK: Pass completion & distribution
  - DF: Tackles & interceptions
  - MF: Progressive passes & shot creation
  - FW: npxG & shots
- **Top 10 Performers**: Real-time leaderboard for current position
- **Distribution Histogram**: Performance spread analysis

## 🎨 Design Features

- **Premium Gradients**: Purple-pink color scheme with glassmorphism effects
- **Smooth Animations**: Micro-interactions on hover and click
- **Responsive Layout**: Works on desktop, tablet, and mobile
- **Dark Mode**: Professional dark theme optimized for data visualization
- **Google Fonts**: Inter for UI, Outfit for headings

## 📦 Data Structure

### Team Data
- Source: `unpivoted_data.xlsx`
- 96 teams across 5 leagues
- 139 metrics per team (PPDA, Field Tilt, Directness, etc.)

### Player Data
- Source: `final_chart_data_long.xlsx`
- 2,338 players
- 19 metrics with raw values, per90, and percentiles
- Metrics: Goals, Assists, xG, xAG, Tackles, Passes, etc.

## 🚀 Usage

### Quick Start
1. Open `index.html` in a modern web browser
2. Or use Python HTTP server:
   ```bash
   python -m http.server 8000
   ```
3. Navigate to `http://localhost:8000`

### Filters Workflow
1. Select league(s) from Core Filters
2. Choose position if analyzing players
3. Adjust minutes played to filter low-usage players
4. Use Comparison Engine to select teams/players
5. Switch between tabs to view different analyses

### Export
Click "Export Data" button to download filtered results as JSON

## 🔄 Dynamic Features

### Real-time Updates
All charts update instantly when:
- Filters are changed
- Teams/players are selected/deselected
- Position is switched
- Metric focus is changed

### Highlight Logic
In scatter plots:
- Selected players/teams shown in vibrant colors
- Non-selected items shown in muted background
- Provides context while highlighting targets

### Percentile Rankings
Player radar charts use percentile ranks (0-100) instead of raw values for fair comparison across different metrics

## 📊 Technical Stack

- **HTML5**: Semantic structure with SEO optimization
- **CSS3**: Custom properties, gradients, animations, grid/flexbox
- **JavaScript ES6+**: Async/await, modules, modern syntax
- **Chart.js 4.4**: Interactive charts with custom styling
- **No frameworks**: Pure vanilla JS for maximum performance

## 🎯 Key Metrics Explained

### Team Metrics
- **PPDA**: Passes Per Defensive Action (lower = more pressing)
- **OPPDA**: Opponent PPDA (how much opponent presses you)
- **Field Tilt**: % of play in opponent's half
- **Directness**: How direct the passing is (vs possession-based)
- **HighError_Rate**: Errors leading to chances
- **BigChance_Diff**: Big chances created vs conceded

### Player Metrics
- **npxG**: Non-penalty expected goals
- **xAG**: Expected assisted goals
- **SCA**: Shot creating actions
- **Progressive Passes/Carries**: Moves ball significantly forward
- **Successful Take-Ons**: Dribbles past opponents
- **Percentile**: Player's rank vs all players in position (0-100)

## 📱 Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Modern mobile browsers

## 🔮 Future Enhancements

- [ ] Real-time data updates
- [ ] PNG/PDF export for charts
- [ ] Custom metric selection for radar charts
- [ ] Player development tracking over seasons
- [ ] Team formation visualizations
- [ ] Heat maps and pitch visualizations

## 👤 Data Sources

- Team statistics from SofaScore and Understat
- Player statistics from FBref
- Processed through custom Python pipelines

---

**Version**: 2.0  
**Last Updated**: January 2026  
**License**: Internal Use

Made with ⚽ and 💜
