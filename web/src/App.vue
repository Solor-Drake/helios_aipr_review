<script setup>
import Home from './views/Home.vue'
</script>

<template>
  <Home />
</template>

<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;700&display=swap');

:root {
  --gold: #d4a017;
  --gold-light: #f0c75e;
  --gold-dark: #8b6914;
  --amber: #ff8c00;
  --bronze: #cd7f32;
  --bg-deep: #0d0d1a;
  --bg-card: rgba(20, 15, 30, 0.92);
  --bg-input: rgba(30, 20, 40, 0.85);
  --text: #e0d8c8;
  --text-dim: #9a9080;
  --text-bright: #ffe8b0;
  --red: #c0392b;
  --yellow: #d4a017;
  --green: #2ecc71;
  --border-gold: 1px solid rgba(212, 160, 23, 0.3);
  --glow-gold: 0 0 20px rgba(212, 160, 23, 0.15);
  --glow-strong: 0 0 40px rgba(212, 160, 23, 0.3);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Noto Sans SC', sans-serif;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(212, 160, 23, 0.12) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 20%, rgba(255, 140, 0, 0.06) 0%, transparent 50%),
    linear-gradient(180deg, #0d0d1a 0%, #121023 40%, #0a0a14 100%);
  background-attachment: fixed;
  color: var(--text);
  min-height: 100vh;
}

.home {
  max-width: 900px;
  margin: 0 auto;
  padding: 30px 20px 60px;
}

h1 {
  text-align: center;
  font-size: 2.2em;
  font-weight: 700;
  background: linear-gradient(180deg, #f0c75e 0%, #d4a017 40%, #8b6914 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 4px;
  text-shadow: none;
  letter-spacing: 2px;
}

.subtitle {
  text-align: center;
  color: var(--text-dim);
  font-size: 0.9em;
  margin-bottom: 32px;
  letter-spacing: 4px;
}

.review-form {
  margin-bottom: 24px;
}

.form-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.form-row input {
  flex: 1;
  min-width: 280px;
  padding: 12px 16px;
  background: var(--bg-input);
  border: var(--border-gold);
  border-radius: 8px;
  color: var(--text-bright);
  font-size: 0.95em;
  outline: none;
  transition: border-color 0.3s, box-shadow 0.3s;
}

.form-row input:focus {
  border-color: var(--gold-light);
  box-shadow: var(--glow-gold);
}

.form-row input::placeholder {
  color: var(--text-dim);
}

.form-row select {
  padding: 12px 14px;
  background: var(--bg-input);
  border: var(--border-gold);
  border-radius: 8px;
  color: var(--text-bright);
  font-size: 0.9em;
  cursor: pointer;
  outline: none;
}

.form-row select option {
  background: #1a1526;
  color: var(--text);
}

button {
  padding: 12px 20px;
  background: linear-gradient(135deg, #8b6914 0%, #d4a017 50%, #8b6914 100%);
  border: none;
  border-radius: 8px;
  color: #1a0a00;
  font-weight: 700;
  font-size: 0.95em;
  cursor: pointer;
  transition: all 0.3s;
  text-shadow: 0 1px 0 rgba(255,255,255,0.1);
}

button:hover:not(:disabled) {
  box-shadow: var(--glow-strong);
  transform: translateY(-1px);
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

button.active {
  background: linear-gradient(135deg, #f0c75e 0%, #ff8c00 100%);
  box-shadow: var(--glow-strong);
}

.error {
  color: #e74c3c;
  margin-top: 8px;
  font-size: 0.9em;
}

.polling {
  text-align: center;
  padding: 24px;
  color: var(--gold-light);
  font-size: 1.1em;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid var(--gold);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.summary {
  text-align: center;
  font-size: 1.1em;
  color: var(--text-bright);
  margin: 16px 0;
  padding: 12px;
  background: var(--bg-card);
  border: var(--border-gold);
  border-radius: 8px;
}

.pending-count {
  text-align: center;
  padding: 8px;
  background: rgba(212, 160, 23, 0.15);
  border: 1px solid var(--gold);
  border-radius: 6px;
  color: var(--gold-light);
  margin-bottom: 16px;
}

.result-tabs {
  margin-top: 20px;
}

.result-tabs nav {
  display: flex;
  gap: 6px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.result-tabs nav button {
  padding: 8px 16px;
  font-size: 0.85em;
  background: var(--bg-card);
  color: var(--text-dim);
  border: var(--border-gold);
  border-radius: 6px;
  transition: all 0.2s;
}

.result-tabs nav button.active {
  background: linear-gradient(135deg, #8b6914, #d4a017);
  color: #1a0a00;
  border-color: var(--gold-light);
}

.count {
  font-size: 0.8em;
  margin-left: 4px;
  opacity: 0.7;
}

.risk-card {
  background: var(--bg-card);
  border: var(--border-gold);
  border-left: 4px solid var(--gold);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  transition: box-shadow 0.3s;
}

.risk-card:hover {
  box-shadow: var(--glow-gold);
}

.risk-card.risk-red {
  border-left-color: var(--red);
}

.risk-card.risk-yellow {
  border-left-color: var(--yellow);
}

.risk-card.risk-green {
  border-left-color: var(--green);
}

.risk-header {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.severity-badge,
.agent-badge,
.repair-badge,
.human-badge {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.75em;
  font-weight: 600;
}

.severity-badge {
  background: rgba(192, 57, 43, 0.2);
  color: #e74c3c;
}

.agent-badge {
  background: rgba(212, 160, 23, 0.15);
  color: var(--gold-light);
}

.repair-badge {
  background: rgba(46, 204, 113, 0.15);
  color: var(--green);
}

.human-badge {
  background: rgba(255, 140, 0, 0.2);
  color: var(--amber);
}

.human-badge.confirmed_fix {
  background: rgba(46, 204, 113, 0.2);
  color: #2ecc71;
}

.human-badge.ai_correct {
  background: rgba(52, 152, 219, 0.2);
  color: #3498db;
}

.human-badge.false_positive {
  background: rgba(149, 165, 166, 0.2);
  color: #95a5a6;
}

.risk-card h4 {
  font-size: 1em;
  color: var(--text-bright);
  margin-bottom: 6px;
}

.file-loc {
  font-size: 0.8em;
  color: var(--text-dim);
  margin-bottom: 8px;
  font-family: monospace;
}

.desc {
  font-size: 0.9em;
  color: var(--text);
  line-height: 1.5;
  margin-bottom: 10px;
}

.suggestion {
  background: rgba(0,0,0,0.3);
  padding: 12px;
  border-radius: 6px;
  font-family: 'Fira Code', monospace;
  font-size: 0.85em;
  color: var(--text-bright);
  overflow-x: auto;
  white-space: pre-wrap;
  line-height: 1.4;
}

.human-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(212, 160, 23, 0.15);
  flex-wrap: wrap;
}

.btn-fix {
  background: linear-gradient(135deg, #1a6b3a, #2ecc71);
}

.btn-correct {
  background: linear-gradient(135deg, #1a4a6b, #3498db);
}

.btn-false {
  background: linear-gradient(135deg, #4a4a4a, #7f8c8d);
}

.comparison-view {
  background: var(--bg-card);
  border: var(--border-gold);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.comparison-view .summary {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
  background: none;
  border: none;
  font-size: 0.95em;
}

.fixed { color: var(--green); }
.new { color: var(--amber); }
.unresolved { color: #e74c3c; }

.comparison-view h4 {
  color: var(--text-bright);
  margin: 12px 0 6px;
}

.comparison-view li {
  font-size: 0.85em;
  color: var(--text-dim);
  margin-left: 20px;
  padding: 2px 0;
}
</style>
