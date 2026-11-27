"""Unified HTML/CSS/JS template for the 萬能采集器 / universal workbench."""

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>__APP_NAME__ · 统一智能采集工作台</title>
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="shortcut icon" href="/favicon.ico">
<link rel="icon" type="image/png" sizes="256x256" href="/app-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<style>
:root{
  --radius-xl:26px;--radius-lg:20px;--radius-md:14px;--radius-sm:10px;
  --ease:220ms cubic-bezier(.22,1,.36,1);
  --spring:360ms cubic-bezier(.22,1.18,.36,1);
}
*{box-sizing:border-box}
::-webkit-scrollbar{width:7px;height:7px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(110,136,162,.34);border-radius:999px}
::-webkit-scrollbar-thumb:hover{background:rgba(110,136,162,.58)}
html,body{margin:0;min-height:100%;font-family:"Microsoft YaHei UI","PingFang SC","Noto Sans CJK SC",sans-serif;-webkit-font-smoothing:antialiased}

body[data-theme="light"]{
  color-scheme:light;
  --bg:#f5f7fb;--panel:#ffffff;--soft:#f0f4f8;--line:#e2e8f0;
  --text:#111827;--muted:#64748b;--primary:#2563eb;--primary-hover:#1d4ed8;--accent:#2563eb;
  --active:#eff6ff;--input:#f8fafc;--ok:#16a34a;--bad:#dc2626;--warn:#d97706;
  --shadow:0 4px 16px rgba(15,23,42,.06);--shadow-hover:0 8px 24px rgba(15,23,42,.10);
  --shadow-small:0 2px 8px rgba(15,23,42,.05);--shadow-inset:inset 0 1px 3px rgba(15,23,42,.06);
  --pill-bg:#ffffff;--pill-border:#e2e8f0;--orb-a:transparent;--orb-b:transparent;
}
body[data-theme="dark"]{
  color-scheme:dark;
  --bg:#0f141c;--panel:#161d27;--soft:#1e2736;--line:#2a3547;
  --text:#f1f5f9;--muted:#94a3b8;--primary:#3b82f6;--primary-hover:#2563eb;--accent:#60a5fa;
  --active:#1e2c42;--input:#0c1118;--ok:#22c55e;--bad:#ef4444;--warn:#f59e0b;
  --shadow:0 6px 20px rgba(0,0,0,.35);--shadow-hover:0 10px 28px rgba(0,0,0,.45);
  --shadow-small:0 2px 10px rgba(0,0,0,.28);--shadow-inset:inset 0 1px 4px rgba(0,0,0,.38);
  --pill-bg:#243145;--pill-border:rgba(148,163,184,.25);--orb-a:transparent;--orb-b:transparent;
}
body[data-theme="neo"]{
  color-scheme:light;
  --bg:#e8edf3;--panel:#e4ecf4;--soft:#dce4ec;--line:#d1dbe4;
  --text:#1f2937;--muted:#5f7287;--primary:#263442;--primary-hover:#17222e;--accent:#436e91;
  --active:#d9e5f0;--input:rgba(255,255,255,.46);--ok:#277b60;--bad:#b24c54;--warn:#c27824;
  --shadow:8px 8px 20px #c7cfd8,-8px -8px 20px #fbfdff;
  --shadow-hover:10px 12px 24px #bfcad5,-10px -10px 24px #ffffff;
  --shadow-small:5px 5px 12px #c7cfd7,-5px -5px 12px #fbfdff;
  --shadow-inset:inset 3px 3px 7px #c8d0d8,inset -3px -3px 7px #f8fbfe;
  --pill-bg:rgba(255,255,255,.78);--pill-border:rgba(255,255,255,.92);--orb-a:transparent;--orb-b:transparent;
}
body[data-theme="neo-dark"]{
  color-scheme:dark;
  --bg:#151c26;--panel:#1c2533;--soft:#232e3f;--line:#2d3b4f;
  --text:#eef3f9;--muted:#95a7be;--primary:#3b82f6;--primary-hover:#2563eb;--accent:#60a5fa;
  --active:#253348;--input:rgba(13,19,28,.55);--ok:#34d399;--bad:#f87171;--warn:#fbbf24;
  --shadow:8px 8px 20px #0d1219,-6px -6px 16px #232f40;
  --shadow-hover:10px 12px 24px #090d12,-7px -7px 18px #283649;
  --shadow-small:5px 5px 12px #0d1219,-4px -4px 10px #243041;
  --shadow-inset:inset 3px 3px 7px #0c1118,inset -3px -3px 7px #243041;
  --pill-bg:rgba(43,61,88,.82);--pill-border:rgba(120,160,210,.26);--orb-a:transparent;--orb-b:transparent;
}
body[data-theme="glass"]{
  color-scheme:light;
  --bg:#dce9f4;--panel:rgba(241,247,252,.74);--soft:rgba(219,233,245,.66);
  --line:rgba(117,149,176,.22);--text:#102b45;--muted:#57738d;--primary:#26699b;--primary-hover:#1d547e;--accent:#3b82c4;
  --active:rgba(255,255,255,.78);--input:rgba(255,255,255,.68);--ok:#1f7a5c;--bad:#ad454f;--warn:#c4751d;
  --shadow:0 14px 36px rgba(72,107,138,.16),inset 0 1px 0 rgba(255,255,255,.75);
  --shadow-hover:0 18px 42px rgba(64,98,128,.22),inset 0 1px 0 rgba(255,255,255,.88);
  --shadow-small:0 6px 16px rgba(72,107,138,.14),inset 0 1px 0 rgba(255,255,255,.72);
  --shadow-inset:inset 2px 2px 6px rgba(103,136,164,.18),inset -2px -2px 6px rgba(255,255,255,.65);
  --pill-bg:rgba(255,255,255,.82);--pill-border:rgba(255,255,255,.95);
  --orb-a:rgba(255,255,255,.72);--orb-b:rgba(125,180,224,.34);
}
body[data-theme="glass-dark"]{
  color-scheme:dark;
  --bg:#0e1a28;--panel:rgba(22,38,58,.72);--soft:rgba(31,52,78,.62);
  --line:rgba(112,163,212,.22);--text:#ecf5ff;--muted:#93b4d4;--primary:#0ea5e9;--primary-hover:#38bdf8;--accent:#38bdf8;
  --active:rgba(46,79,116,.68);--input:rgba(12,24,38,.66);--ok:#2dd4bf;--bad:#fb7185;--warn:#fbbf24;
  --shadow:0 16px 40px rgba(3,8,16,.46),inset 0 1px 0 rgba(186,230,253,.14);
  --shadow-hover:0 20px 46px rgba(3,8,16,.56),inset 0 1px 0 rgba(186,230,253,.22);
  --shadow-small:0 6px 16px rgba(3,8,16,.34),inset 0 1px 0 rgba(186,230,253,.12);
  --shadow-inset:inset 2px 2px 6px rgba(4,10,18,.52),inset -2px -2px 6px rgba(80,126,172,.14);
  --pill-bg:rgba(38,69,104,.74);--pill-border:rgba(125,211,252,.28);
  --orb-a:rgba(14,165,233,.20);--orb-b:rgba(56,189,248,.14);
}

body{background:var(--bg);color:var(--text);padding:20px 24px 28px;transition:background var(--ease),color var(--ease)}
body[data-theme="glass"]:before,body[data-theme="glass-dark"]:before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(circle at 12% 14%,var(--orb-a),transparent 36%),radial-gradient(circle at 86% 80%,var(--orb-b),transparent 38%);
}
body[data-theme="glass"] .surface,body[data-theme="glass"] .side-nav,body[data-theme="glass"] .topbar,
body[data-theme="glass-dark"] .surface,body[data-theme="glass-dark"] .side-nav,body[data-theme="glass-dark"] .topbar{
  backdrop-filter:blur(22px) saturate(140%);-webkit-backdrop-filter:blur(22px) saturate(140%);
}
.shell{position:relative;z-index:1;max-width:1580px;min-height:calc(100vh - 48px);margin:0 auto;display:flex;flex-direction:column}

/* Top Bar */
.topbar{
  display:flex;align-items:center;justify-content:space-between;gap:14px;
  padding:12px 18px;margin-bottom:18px;border-radius:22px;
  background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow-small);
  transition:background var(--ease),box-shadow var(--ease),border-color var(--ease);
}
.brand{display:flex;align-items:center;gap:13px;min-width:0}
.mark{
  width:42px;height:42px;border-radius:14px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;
  box-shadow:0 8px 18px rgba(38,90,145,.26),inset 0 1px 1px rgba(255,255,255,.45);
  font-family:Georgia,serif;font-size:20px;font-weight:700;flex:0 0 auto;
}
.brand h1{font-size:20px;line-height:1.15;margin:0;letter-spacing:-.3px}
.brand p{margin:3px 0 0;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.top-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;justify-content:flex-end}

.pill-btn{
  display:inline-flex;align-items:center;gap:7px;white-space:nowrap;
  border:1px solid var(--line);background:var(--panel);color:var(--text);
  box-shadow:var(--shadow-small);border-radius:999px;padding:8px 14px;cursor:pointer;
  font:inherit;font-size:12px;font-weight:700;
  transition:transform var(--spring),box-shadow var(--ease),background var(--ease),border-color var(--ease);
}
.pill-btn:hover{transform:translateY(-1.5px);box-shadow:var(--shadow-hover)}
.pill-btn:active{transform:translateY(1px) scale(.985);box-shadow:var(--shadow-inset)}
.pill-btn:disabled{opacity:.58;cursor:not-allowed;transform:none}
.led-dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 4px rgba(39,123,96,.18);transition:background var(--ease)}
.collector-switch[aria-checked="false"] .led-dot{background:var(--bad);box-shadow:0 0 0 4px rgba(178,76,84,.16)}
.engine-pill[data-online="false"] .led-dot{background:var(--muted);box-shadow:0 0 0 4px rgba(120,140,160,.16)}
.engine-pill[data-verify="true"] .led-dot{background:var(--warn);box-shadow:0 0 0 5px rgba(245,158,11,.22);animation:pulse 1.5s infinite}

/* Global Engine Alert Banner */
.alert-banner{
  display:none;align-items:center;justify-content:space-between;gap:14px;
  padding:12px 18px;margin-bottom:16px;border-radius:18px;
  background:var(--panel);border:1px solid var(--warn);box-shadow:var(--shadow-small);font-size:13px;
}
.alert-banner.show{display:flex;animation:panel-in 260ms var(--spring)}

/* Main App Grid */
.app-layout{display:grid;grid-template-columns:212px minmax(0,1fr);gap:18px;align-items:stretch;flex:1}
.side-nav{
  position:sticky;top:18px;display:flex;flex-direction:column;gap:8px;
  min-height:calc(100vh - 132px);padding:14px 10px;border:1px solid var(--line);border-radius:22px;
  background:var(--panel);box-shadow:var(--shadow-small);
}
.nav-caption{padding:4px 10px 4px;color:var(--muted);font-size:11px;font-weight:800;letter-spacing:.08em}
.nav-items{position:relative;display:flex;flex-direction:column;gap:4px}
.nav-liquid-pill{
  position:absolute;left:0;right:0;top:0;height:48px;border-radius:14px;
  background:var(--pill-bg);border:1px solid var(--pill-border);box-shadow:var(--shadow-small);
  pointer-events:none;z-index:0;opacity:0;
  transition:transform var(--spring),height var(--spring),opacity 180ms ease;
}
.nav-liquid-pill:before{
  content:"";position:absolute;left:6px;top:24%;bottom:24%;width:3.5px;border-radius:4px;background:var(--accent);
}
.nav-item{
  position:relative;z-index:1;width:100%;display:grid;gap:2px;text-align:left;
  border:0;border-radius:14px;background:transparent;color:var(--text);
  padding:10px 12px 10px 16px;cursor:pointer;font:inherit;
  transition:color var(--ease),transform var(--spring);
}
.nav-item span{font-size:13px;font-weight:800}.nav-item small{color:var(--muted);font-size:10.5px;line-height:1.35}
.nav-item:hover{transform:translateX(2px)}
.nav-item[aria-selected="true"] span{color:var(--accent)}
.nav-footer{margin-top:auto;padding:10px 4px 2px;border-top:1px solid var(--line);display:grid;gap:8px}
.nav-tip{margin:0 2px;color:var(--muted);font-size:11px;line-height:1.5}

.workspace{display:flex;flex-direction:column;gap:18px;min-width:0}
.workspace>div{display:flex;flex-direction:column;flex:1;min-width:0}
.surface{
  background:var(--panel);border:1px solid var(--line);border-radius:var(--radius-xl);
  box-shadow:var(--shadow);padding:24px;min-width:0;
  transition:background var(--ease),box-shadow var(--ease),border-color var(--ease);
}
.work-panel{display:none;min-width:0}.work-panel.active{display:flex;flex-direction:column;flex:1;min-height:calc(100vh - 132px);animation:panel-in 300ms var(--spring)}

.eyebrow{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px}
.eyebrow:before{content:"";width:22px;height:2.5px;border-radius:2px;background:var(--accent)}
h2{font-size:24px;line-height:1.25;margin:0 0 6px;letter-spacing:-.4px}
.lead{margin:0 0 18px;color:var(--muted);line-height:1.65;font-size:13px}
label{display:block;font-size:12px;font-weight:700;margin-bottom:6px;color:var(--text)}

textarea,input[type="text"],input[type="password"],input[type="number"],input[type="url"],input[type="datetime-local"],select{
  width:100%;border:1px solid var(--line);background:var(--input);color:var(--text);
  border-radius:var(--radius-md);outline:none;box-shadow:var(--shadow-inset);
  font:inherit;font-size:13px;transition:border-color var(--ease),box-shadow var(--ease);
}
textarea{min-height:130px;padding:13px 14px;resize:vertical;line-height:1.65}
input[type="text"],input[type="password"],input[type="number"],input[type="url"],input[type="datetime-local"],select{height:38px;padding:0 11px}
textarea:focus,input:focus,select:focus{border-color:var(--accent);box-shadow:var(--shadow-inset),0 0 0 3px rgba(59,130,246,.16)}

/* Segmented Switch */
.seg-group{
  display:inline-flex;align-items:center;gap:4px;padding:4px;border-radius:999px;
  background:var(--soft);border:1px solid var(--line);box-shadow:var(--shadow-inset);
}
.seg-btn{
  border:0;background:transparent;color:var(--muted);border-radius:999px;
  padding:6px 14px;font:inherit;font-size:12px;font-weight:700;cursor:pointer;
  transition:background var(--spring),color var(--ease),box-shadow var(--ease),transform var(--spring);
}
.seg-btn.active{background:var(--pill-bg);color:var(--text);box-shadow:var(--shadow-small)}
.seg-btn:active{transform:scale(.96)}

/* Buttons */
.btn-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:16px}
.primary{
  flex:1;min-width:170px;height:46px;border:0;border-radius:15px;
  background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;
  font:inherit;font-size:14px;font-weight:800;letter-spacing:.03em;cursor:pointer;
  box-shadow:0 10px 22px rgba(32,68,112,.22),inset 0 1px 0 rgba(255,255,255,.32);
  transition:transform var(--spring),box-shadow var(--ease),filter var(--ease);
}
.primary:hover{transform:translateY(-1.5px);box-shadow:0 14px 28px rgba(32,68,112,.28);filter:brightness(1.05)}
.primary:active{transform:translateY(1px) scale(.985)}
.primary:disabled{opacity:.55;cursor:not-allowed;transform:none}
.secondary{
  height:42px;padding:0 15px;border:1px solid var(--line);border-radius:13px;
  background:var(--panel);color:var(--text);box-shadow:var(--shadow-small);
  font:inherit;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;
  transition:transform var(--spring),box-shadow var(--ease);
}
.secondary:hover{transform:translateY(-1px);box-shadow:var(--shadow-hover)}
.secondary:active{transform:translateY(1px) scale(.985);box-shadow:var(--shadow-inset)}
.secondary.danger{color:var(--bad)}
.mini-btn{
  padding:5px 10px;border:1px solid var(--line);border-radius:9px;background:var(--panel);
  color:var(--text);font:inherit;font-size:11.5px;font-weight:700;cursor:pointer;white-space:nowrap;
  box-shadow:var(--shadow-small);transition:transform var(--spring),box-shadow var(--ease);
}
.mini-btn:hover{transform:translateY(-1px);box-shadow:var(--shadow-hover)}
.mini-btn:active{transform:scale(.96)}

/* Toolbar & Tables */
.panel-head-row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.toolbar .search-box{flex:1;min-width:160px;max-width:250px}
.toolbar select.sort-select{width:auto;min-width:116px;height:34px;padding:0 10px;border-radius:10px;font-size:12px;font-weight:700}
.toolbar select.group-select{min-width:128px;max-width:185px;font-weight:800}
.toolbar select.group-select[data-filtered="true"]{border-color:var(--accent);color:var(--accent)}
.more-menu{position:relative;display:inline-block}
.more-menu summary{list-style:none;padding:5px 10px;border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--text);font:inherit;font-size:11.5px;font-weight:700;cursor:pointer;white-space:nowrap;box-shadow:var(--shadow-small)}
.more-menu summary::-webkit-details-marker{display:none}
.more-pop{position:absolute;right:0;top:calc(100% + 4px);z-index:40;min-width:154px;padding:6px;border-radius:12px;background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow-hover);display:grid;gap:4px}
.more-pop button{width:100%;text-align:left;border:0;background:transparent;color:var(--text);padding:7px 10px;border-radius:8px;font:inherit;font-size:12px;font-weight:600;cursor:pointer}
.more-pop button:hover{background:var(--active)}
.theme-menu-wrap{position:relative;display:inline-block}
.theme-popover{position:absolute;right:0;top:calc(100% + 8px);z-index:60;width:248px;padding:8px;border-radius:16px;background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow-hover);display:grid;gap:4px;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
.theme-popover[hidden]{display:none}
.theme-opt{width:100%;display:grid;gap:2px;text-align:left;border:1px solid transparent;background:transparent;color:var(--text);padding:8px 11px;border-radius:11px;font:inherit;cursor:pointer;transition:background var(--ease),border-color var(--ease)}
.theme-opt:hover{background:var(--soft)}
.theme-opt.active{background:var(--active);border-color:var(--accent)}
.theme-opt strong{font-size:12.5px;font-weight:800}.theme-opt small{font-size:11px;color:var(--muted)}
.quick-launch-card{margin:12px 0;padding:16px;border-radius:18px;background:var(--soft);border:1px solid var(--line);box-shadow:var(--shadow-small);display:grid;gap:12px}
.param-chips{display:flex;align-items:stretch;gap:10px;flex-wrap:wrap}
.param-chip{display:inline-flex;align-items:center;gap:8px;padding:7px 12px;border-radius:12px;background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow-small);font-size:12px;font-weight:700}
.param-chip input[type="number"]{width:68px;height:30px;padding:0 8px;text-align:center;font-weight:800;font-variant-numeric:tabular-nums;border-radius:9px}
.kpi-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.kpi-card{padding:7px 10px;border-radius:11px;background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow-inset);display:flex;align-items:center;justify-content:space-between;gap:6px}
.kpi-label{font-size:11px;font-weight:700;color:var(--muted)}
.kpi-value{font-size:16px;font-weight:800;line-height:1.15;color:var(--text);font-variant-numeric:tabular-nums}
.kpi-card.accent .kpi-value{color:var(--accent)}
.kpi-card.ok .kpi-value{color:var(--ok)}
@media(max-width:680px){.kpi-strip{grid-template-columns:repeat(2,minmax(0,1fr))}}
.table-wrap{
  flex:1;min-height:260px;max-height:calc(100vh - 340px);
  border:1px solid var(--line);border-radius:16px;background:var(--input);
  box-shadow:var(--shadow-inset);overflow:auto;margin-bottom:8px;
}
table.data-table{width:100%;border-collapse:collapse;font-size:12px}
table.data-table th{
  position:sticky;top:0;z-index:2;background:var(--soft);color:var(--text);
  font-weight:800;text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;
}
table.data-table td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
table.data-table tr:last-child td{border-bottom:0}
table.data-table tbody tr{transition:background 140ms ease}
table.data-table tbody tr:hover{background:var(--active)}
.cell-ellipsis{max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge{
  display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;
  background:var(--active);color:var(--text);border:1px solid var(--line);white-space:nowrap;
}
.badge.dy{color:var(--accent)}.badge.xhs{color:var(--bad)}.badge.jg{color:#b45309}.badge.ok{color:var(--ok)}.badge.warn{color:var(--warn)}

/* Collapsible Filter Drawer */
details.drawer{
  margin-top:12px;border:1px solid var(--line);border-radius:16px;
  background:var(--soft);padding:0 14px;transition:background var(--ease);
}
details.drawer summary{
  list-style:none;padding:12px 0;font-size:13px;font-weight:800;cursor:pointer;
  display:flex;align-items:center;justify-content:space-between;color:var(--text);
}
details.drawer summary:after{content:"▾";font-size:13px;color:var(--muted);transition:transform var(--spring)}
details.drawer[open] summary:after{transform:rotate(180deg)}
.drawer-body{padding:4px 0 14px;display:grid;gap:12px;border-top:1px solid var(--line)}
.check-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:8px 12px}
.check-item{display:flex;align-items:center;gap:7px;font-size:12px;font-weight:600;margin:0;cursor:pointer}
.check-item input[type="checkbox"],.check-item input[type="radio"]{width:15px;height:15px;margin:0;box-shadow:none;accent-color:var(--accent);flex:0 0 auto}
.num-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px}
.num-row input[type="number"]{width:74px;height:32px;padding:0 8px}
.num-row input[type="datetime-local"]{width:185px;height:32px}
.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.form-grid .wide{grid-column:1/-1}

/* Inline Progress Panel */
.live-progress{
  margin-top:12px;padding:12px 14px;border-radius:15px;background:var(--soft);
  border:1px solid var(--line);display:grid;gap:8px;
}
.progress-track{height:9px;border-radius:999px;background:var(--input);box-shadow:var(--shadow-inset);overflow:hidden;position:relative}
.progress-bar{
  height:100%;width:0;border-radius:inherit;position:relative;
  background:linear-gradient(90deg,var(--primary),var(--accent));
  transition:width 420ms var(--spring);
}
.progress-bar.active:after{
  content:"";position:absolute;inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.45),transparent);
  animation:shimmer 1.15s infinite;
}
.progress-meta{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--muted);gap:8px;flex-wrap:wrap}

/* Inline Status & Task Cards */
.card-compact{padding:16px 18px}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.panel-title{font-size:15px;font-weight:800;margin:0}.panel-sub{font-size:11.5px;color:var(--muted);margin:4px 0 0;line-height:1.45}
.count-badge{min-width:38px;height:32px;padding:0 10px;display:grid;place-items:center;border-radius:11px;background:var(--active);color:var(--text);font-size:16px;font-weight:800;box-shadow:var(--shadow-small)}
.scroll-list{display:flex;flex-direction:column;gap:8px;margin-top:12px;max-height:220px;overflow:auto;padding:2px}
.task-row{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:10px 11px;border:1px solid var(--line);border-radius:12px;background:var(--soft);font-size:12px;line-height:1.45}
.task-main{min-width:0;flex:1}.task-title{display:block;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-meta{display:block;color:var(--muted);margin-top:2px;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.state-dot{width:10px;height:10px;border-radius:50%;background:var(--muted);box-shadow:0 0 0 5px rgba(130,150,170,.14);flex:0 0 auto;margin-top:4px}
.state-dot.running{background:var(--accent);animation:pulse 1.5s infinite}.state-dot.done{background:var(--ok)}.state-dot.error{background:var(--bad)}
.results{display:none;gap:8px;flex-direction:column;max-height:240px;overflow:auto;margin-top:10px}.results.show{display:flex}
.result{padding:10px 12px;border-radius:12px;background:var(--soft);border:1px solid var(--line);font-size:12px}
.result.ok{border-left:3px solid var(--ok)}.result.fail{border-left:3px solid var(--bad)}
.collection-status{margin-top:10px;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--soft);font-size:12px;color:var(--muted)}
.collection-status[hidden],#downloadRecovery[hidden]{display:none}
.collection-status[data-state="error"],.collection-status[data-state="verification_required"]{border-color:var(--bad);color:var(--bad)}

/* Login Cards & Theme Cards */
.login-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin-bottom:14px}
.login-card,.theme-card{
  padding:15px;border-radius:16px;border:1px solid var(--line);background:var(--soft);
  box-shadow:var(--shadow-small);display:grid;gap:8px;cursor:pointer;
  transition:transform var(--spring),box-shadow var(--ease),border-color var(--ease);
}
.login-card:hover,.theme-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-hover)}
.theme-card.active{border-color:var(--accent);background:var(--active)}
.subtabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}
.subpanel{display:none}.subpanel.active{display:block;animation:panel-in 240ms var(--spring)}

/* Dialog & Modal */
.settings-dialog{width:min(460px,calc(100vw - 32px));max-width:none;border:1px solid var(--line);border-radius:22px;background:var(--panel);color:var(--text);padding:22px;box-shadow:var(--shadow-hover)}
.settings-dialog::backdrop{background:rgba(12,18,28,.38);backdrop-filter:blur(5px)}
.dialog-heading{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.dialog-heading h2{font-size:20px;margin:0}.dialog-heading p{margin:0 0 4px;color:var(--muted);font-size:12px}
.dialog-close{width:34px;height:34px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--text);font-size:18px;cursor:pointer}
.footnote{text-align:center;color:var(--muted);font-size:11px;margin-top:18px}
.toast{
  position:fixed;left:50%;bottom:24px;z-index:99;padding:10px 18px;border-radius:999px;
  border:1px solid var(--line);background:var(--panel);color:var(--text);
  box-shadow:var(--shadow-hover);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);
  font-size:12.5px;font-weight:700;opacity:0;pointer-events:none;
  transform:translate(-50%,16px) scale(.96);transition:opacity var(--ease),transform var(--spring);
}
.toast.show{opacity:1;transform:translate(-50%,0) scale(1)}
.toast.err{border-color:var(--bad);color:var(--bad)}

@keyframes pulse{0%,100%{box-shadow:0 0 0 4px rgba(59,130,246,.22)}50%{box-shadow:0 0 0 9px rgba(59,130,246,.04)}}
@keyframes shimmer{0%{transform:translateX(-110%)}100%{transform:translateX(220%)}}
@keyframes panel-in{from{opacity:0;transform:translateY(6px) scale(.992)}to{opacity:1;transform:translateY(0) scale(1)}}
@media(max-width:1180px){.workspace{grid-template-columns:1fr}}
@media(max-width:860px){.app-layout{grid-template-columns:1fr}.side-nav{position:static}.nav-items{flex-direction:row;flex-wrap:wrap}.nav-liquid-pill{display:none}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}
</style>
</head>
<body data-theme="neo">
<main class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="mark">∞</div>
      <div>
        <h1>__APP_NAME__ · 统一采集中心</h1>
        <p>抖音 + 小红书 + 公开链接 + 剪贴板 + AI CLI/MCP 一体化工作台</p>
      </div>
    </div>
    <div class="top-actions">
      <button class="pill-btn engine-pill" id="engineStatusPill" type="button" data-online="false" data-verify="false" title="点击跳转登录与引擎状态页">
        <span class="led-dot"></span><span id="engineStatusText">引擎检测中</span>
      </button>
      <button class="pill-btn collector-switch" id="collectorToggle" type="button" role="switch" aria-checked="true" title="独立后台监控剪贴板；每条复制内容自动入队采集">
        <span class="led-dot"></span><span id="collectorToggleText">剪贴板采集 开</span>
      </button>
      <button class="pill-btn" id="themeButton" type="button" aria-label="切换视觉主题" title="点击切换下一主题（自动切换 / 浅色拟态 / 深色拟态 / 浅色玻璃 / 深色玻璃）">主题：自动切换</button>
    </div>
  </header>

  <div class="alert-banner" id="globalEngineAlert">
    <div><strong id="alertTitle">底层采集引擎离线</strong> <span id="alertBody" style="color:var(--muted)">公开单链接可直接使用；使用抖音/小红书搜索与主页发现前请先启动引擎或确认登录态。</span></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="mini-btn" id="btnBannerStartDouyin" type="button">启动抖音引擎</button>
      <button class="mini-btn" id="btnBannerPopBrowser" type="button" hidden>弹出并置顶验证窗口</button>
      <button class="mini-btn" id="btnBannerResume" type="button" hidden>已完成验证，继续采集</button>
      <button class="mini-btn" id="btnBannerVerify" type="button">前往登录/验证</button>
    </div>
  </div>

  <div class="app-layout">
    <aside class="side-nav" aria-label="采集入口">
      <div class="nav-caption">功能导航</div>
      <div class="nav-items" id="navItems" role="tablist" aria-orientation="vertical">
        <div class="nav-liquid-pill" id="navLiquidPill"></div>
        <button class="nav-item" id="tabSingle" type="button" role="tab" aria-selected="false" data-panel="singlePanel"><span>单作品采集</span><small>万能公开链接 + 智能提取</small></button>
        <button class="nav-item" id="tabKeyword" type="button" role="tab" aria-selected="true" data-panel="keywordPanel"><span>关键词采集</span><small>词表管理 · 图文筛选</small></button>
        <button class="nav-item" id="tabHomepage" type="button" role="tab" aria-selected="false" data-panel="homepagePanel"><span>主页采集</span><small>作者库 · 批量主页提取</small></button>
        <button class="nav-item" id="tabArtworks" type="button" role="tab" aria-selected="false" data-panel="artworksPanel"><span>作品列表</span><small>当前/历史 · 剪贴板与AI记录</small></button>
        <button class="nav-item" id="tabLogin" type="button" role="tab" aria-selected="false" data-panel="loginPanel"><span>平台登录</span><small>抖音 · 小红书 · 聚光会话</small></button>
        <button class="nav-item" id="tabSettings" type="button" role="tab" aria-selected="false" data-panel="settingsPanel"><span>下载与软件设置</span><small>路径入库 · 模板通知 · AI 接入</small></button>
      </div>
      <div class="nav-footer">
        <button class="secondary" type="button" style="width:100%;height:36px" onclick="openDownloadDir()">打开作品保存目录</button>
        <p class="nav-tip">所有入口共享同一保存目录、本地去重账本与统一采集内核。</p>
      </div>
    </aside>

    <section class="workspace">
      <div style="min-width:0">
        <!-- 1. 单作品采集 -->
        <section class="surface work-panel" id="singlePanel" role="tabpanel" hidden>
          <div class="eyebrow">Single & Batch Media</div>
          <div class="panel-head-row">
            <div><h2>单作品与批量链接采集</h2><p class="lead">直接粘贴包含作品链接的任意分享文案，系统会自动识别平台并提取全部链接无水印下载（抖音优先免 Cookie 原画秒解，遇风控自动切内置浏览器兜底）。</p></div>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin:2px 0 12px 0">
            <span class="badge dy">抖音（原画秒解/图文/实况）</span>
            <span class="badge xhs">小红书</span>
            <span class="badge">快手</span>
            <span class="badge">B站</span>
            <span class="badge">微博</span>
            <span class="badge">今日头条</span>
            <span class="badge">豆包 AI</span>
            <span class="badge">即梦 AI</span>
            <span class="badge">皮皮虾 / 皮皮搞笑 / 最右</span>
            <span class="badge">YouTube / X / TikTok / IG / Reddit</span>
          </div>
          <label for="input">分享文案或作品链接（支持随便粘贴整段带废话的分享文本，自动提取全部 http 链接）</label>
          <textarea id="input" rows="6" placeholder="直接把整段分享文案粘贴到这里即可（无需删废话、无需手动分行，系统会自动识别并提取里面所有 http(s):// 链接）：&#10;• 核心平台：抖音（免 Cookie 原画秒解/图文/实况）、小红书（图文/视频/实况）、B站&#10;• 国内与 AI 视频：快手、微博、今日头条、豆包 AI、即梦 AI、皮皮虾、皮皮搞笑、最右&#10;• 海外平台：YouTube、X (Twitter)、TikTok、Instagram、Facebook、Pinterest、Reddit、Vimeo"></textarea>
          <div class="btn-row">
            <button class="primary" id="go" type="button">立即解析并下载</button>
          </div>
          <div class="quick-launch-card" style="margin-top:16px" aria-live="polite">
            <div class="panel-head">
              <div><p class="panel-title" style="font-size:13.5px">下载任务进度</p><p class="panel-sub" id="statusSub">等待任务开始</p></div>
              <div style="display:flex;align-items:center;gap:10px">
                <button class="mini-btn" type="button" onclick="openArtworkView('history')">查看历史档案 →</button>
                <span class="state-dot" id="stateDot"></span>
              </div>
            </div>
            <div class="live-progress" style="margin-top:6px">
              <div class="progress-track"><div class="progress-bar" id="progressBar"></div></div>
              <div class="progress-meta"><span id="progressText">已处理 0 / 0</span><span id="successText">成功 0 · 跳过 0 · 失败 0</span></div>
            </div>
            <div class="btn-row" id="downloadRecovery" style="margin-top:8px" hidden>
              <button class="mini-btn" type="button" id="retryFailedDownload">仅重试失败项</button>
              <button class="mini-btn" type="button" id="resumeRemainingDownload">下载剩余未处理</button>
            </div>
            <div class="results" id="results"></div>
          </div>
        </section>

        <!-- 2. 关键词采集 -->
        <section class="surface work-panel active" id="keywordPanel" role="tabpanel">
          <div class="eyebrow">Keyword Collection</div>
          <div class="panel-head-row">
            <div><h2>关键词矩阵采集</h2><p class="lead">直接输入关键词或勾选下方词表开跑；支持无水印直下、历史去重跳过与自动分类入库。</p></div>
            <div class="seg-group" id="kwPlatformSeg">
              <button class="seg-btn active" type="button" data-plat="douyin">抖音</button>
              <button class="seg-btn" type="button" data-plat="xiaohongshu">小红书</button>
              <button class="seg-btn" type="button" data-plat="juguang">小红书聚光</button>
            </div>
          </div>

          <div class="quick-launch-card" id="kwLaunchCard">
            <div class="form-grid">
              <div>
                <label for="keywordValue">立即采集关键词（留空则按顺序采集下方已勾选关键词）</label>
                <input id="keywordValue" type="text" maxlength="100" placeholder="输入单个关键词直接开跑；或勾选下方表格多词自动排队">
              </div>
              <div style="display:flex;gap:8px;align-items:end">
                <div style="flex:1"><label for="kwBatchInput">快速添加到当前分组（逗号或空格分隔）</label><input id="kwBatchInput" type="text" placeholder="新词自动加入当前选中分组，点右侧添加"></div>
                <button class="secondary" type="button" style="height:38px" onclick="kwAddFromInput()">添加词条</button>
              </div>
            </div>

            <div class="param-chips">
              <div class="param-chip"><span>目标套数 (0=全部)</span><input type="number" id="keywordCount" min="0" max="500" value="20"></div>
              <div class="param-chip"><span>作品类型</span><select id="k_media_type" style="width:auto;height:30px;padding:0 8px;border-radius:9px;font-weight:700"><option value="image" selected>仅图文</option><option value="video">仅视频</option><option value="all">全部（图文+视频）</option></select></div>
              <div class="param-chip" id="kwImgRangeChip"><span>图文张数</span><input type="number" id="minImages" min="0" max="50" value="4"><span>至</span><input type="number" id="maxImages" min="0" max="50" value="20"><span>张</span></div>
              <div class="param-chip" id="kwStdSortChip"><span>排序</span><select id="k_web_sort" style="width:auto;height:30px;padding:0 8px;border-radius:9px;font-weight:700"><option value="综合排序">综合排序</option><option value="最多点赞">最多点赞</option><option value="最新发布">最新发布</option></select></div>
              <div class="param-chip" id="kwStdTimeChip"><span>发布时间</span><select id="k_web_publish_time" style="width:auto;height:30px;padding:0 8px;border-radius:9px;font-weight:700"><option value="不限">时间不限</option><option value="一天内">一天内</option><option value="一周内">一周内</option><option value="半年内">半年内</option></select></div>
              <div class="param-chip" id="kwJuguangCatChip" style="display:none"><span>聚光分类</span><select id="k_juguang_category" style="width:auto;height:30px;padding:0 8px;border-radius:9px;font-weight:700"><option value="客资收集" selected>客资收集</option><option value="产品种草">产品种草</option><option value="商品销量">商品销量</option><option value="直播推广">直播推广</option><option value="全部">全部榜单</option></select></div>
              <div class="param-chip" id="kwJuguangTimeChip" style="display:none"><span>时间范围</span><select id="k_juguang_time" style="width:auto;height:30px;padding:0 8px;border-radius:9px;font-weight:700"><option value="近7日" selected>近7日</option><option value="近30日">近30日</option><option value="近90日">近90日</option><option value="近1日">近1日</option><option value="不限">时间不限</option></select></div>
              <div class="param-chip" id="kwJuguangSortChip" style="display:none"><span>筛选标准</span><select id="k_juguang_sort" style="width:auto;height:30px;padding:0 8px;border-radius:9px;font-weight:700"><option value="阅读量" selected>阅读量</option><option value="评论量">评论量</option><option value="点赞量">点赞量</option><option value="收藏量">收藏量</option><option value="互动量">互动量</option><option value="综合排序">综合排序</option></select></div>
              <label class="param-chip" style="cursor:pointer"><input type="checkbox" id="k_direct_download" checked style="width:15px;height:15px;margin:0;accent-color:var(--accent)"> 提取直接下载</label>
              <label class="param-chip" style="cursor:pointer"><input type="checkbox" id="k_skip_dup_chip" checked style="width:15px;height:15px;margin:0;accent-color:var(--accent)"> 已采去重</label>
              <label class="param-chip" style="cursor:pointer"><input type="checkbox" id="k_auto_ingest_chip" checked style="width:15px;height:15px;margin:0;accent-color:var(--accent)"> 自动分类入库</label>
            </div>

            <div class="btn-row" style="margin-top:0">
              <button class="primary" id="startKeyword" type="button">开始关键词采集</button>
              <button class="secondary danger" type="button" onclick="stopKeywordCollection()">停止采集</button>
              <button class="secondary" type="button" onclick="engineAction('bring_verify_browser',{platform:activeKwPlatform,topmost:false})">查看采集浏览器</button>
            </div>

            <div class="kpi-strip" aria-label="关键词采集计数面板">
              <div class="kpi-card"><span class="kpi-label">目标数量</span><strong class="kpi-value" id="kwKpiTarget">20</strong></div>
              <div class="kpi-card"><span class="kpi-label">已扫描卡片</span><strong class="kpi-value" id="kwKpiCrawled">0</strong></div>
              <div class="kpi-card accent"><span class="kpi-label">合格作品</span><strong class="kpi-value" id="kwKpiQualified">0</strong></div>
              <div class="kpi-card ok"><span class="kpi-label">已下载落盘</span><strong class="kpi-value" id="kwKpiDownloaded">0</strong></div>
            </div>

            <div class="live-progress" style="margin-top:0">
              <div class="progress-track"><div class="progress-bar" id="kwVisualBar"></div></div>
              <div class="progress-meta">
                <span id="kwProgressSummary">等待开始采集</span>
                <div style="display:flex;gap:6px">
                  <button class="mini-btn" type="button" onclick="openArtworkView('current')">当前采集列表</button>
                  <button class="mini-btn" type="button" onclick="openArtworkView('history')">历史采集列表</button>
                </div>
              </div>
            </div>
            <p class="panel-sub" id="keywordCapability" style="margin:0">正在检测内置 Edge 采集核心…</p>
            <div class="collection-status" id="keywordStatus" role="status" hidden style="margin:0"></div>
          </div>

          <div class="toolbar" style="margin-top:14px">
            <select class="sort-select group-select" id="kwGroupFilter" data-filtered="false" onchange="onKwGroupChange(this.value)" title="按分组筛选"><option value="all">全部分组</option></select>
            <button class="mini-btn" type="button" onclick="openGroupManager('keywords')" title="新建、重命名或删除分组">分组管理</button>
            <button class="mini-btn" type="button" onclick="kwBatch('all')">全选本组</button>
            <button class="mini-btn" type="button" onclick="kwBatch('invert')">反选</button>
            <button class="mini-btn" type="button" onclick="kwBatch('none')">清空</button>
            <input class="search-box" type="text" id="kwSearch" placeholder="搜索关键词、分组或备注…" oninput="refreshKeywords()">
            <select class="sort-select" id="kwSortBy" onchange="refreshKeywords()" title="选择关键词排序规则">
              <option value="seq">按序号</option>
              <option value="keyword">按关键词</option>
              <option value="last_count">按上次数量</option>
              <option value="recorded_ids">按记录ID数</option>
              <option value="last_time">按最近时间</option>
              <option value="group">按分组名</option>
            </select>
            <button class="mini-btn" id="kwSortDirBtn" type="button" onclick="toggleKwSortDir()" title="切换升序/降序">↑ 升序</button>
            <input type="file" id="kwFileInput" accept=".txt,.csv" hidden onchange="kwImportFile(this)">
            <button class="mini-btn" type="button" onclick="$('kwFileInput').click()">导入(.txt/.csv)</button>
            <button class="mini-btn" type="button" onclick="kwAssignGroupPrompt()">分配分组</button>
            <button class="mini-btn danger" type="button" onclick="kwDeleteSelected()">删除选中</button>
            <details class="more-menu" id="kwMoreMenu">
              <summary>更多 ▾</summary>
              <div class="more-pop">
                <button type="button" onclick="openGroupManager('keywords');this.closest('details').removeAttribute('open')">分组管理</button>
                <button type="button" onclick="kwImportPreset();this.closest('details').removeAttribute('open')">导入江浙沪46词</button>
                <button type="button" onclick="kwRemarkPrompt();this.closest('details').removeAttribute('open')">修改备注</button>
                <button type="button" onclick="kwExport();this.closest('details').removeAttribute('open')">导出词表 (.csv)</button>
              </div>
            </details>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>选择</th><th>序号</th><th>平台</th><th>分组</th><th>关键词</th><th>上次提取</th><th>上次数量</th><th>记录ID</th><th>备注</th><th>上次时间</th><th>操作</th></tr></thead>
              <tbody id="kwTableBody"><tr><td colspan="11" style="text-align:center;color:var(--muted)">正在加载关键词列表…</td></tr></tbody>
            </table>
          </div>
        </section>

        <!-- 3. 主页采集 -->
        <section class="surface work-panel" id="homepagePanel" role="tabpanel" hidden>
          <div class="eyebrow">Author Homepage</div>
          <div class="panel-head-row">
            <div><h2>作者主页采集</h2><p class="lead">按项目分组管理抖音 / 小红书关注作者档案，粘贴或勾选主页链接，一键抓取公开图文与视频。</p></div>
            <div class="seg-group" id="auPlatformSeg">
              <button class="seg-btn active" type="button" data-plat="douyin">抖音</button>
              <button class="seg-btn" type="button" data-plat="xiaohongshu">小红书</button>
            </div>
          </div>

          <div class="quick-launch-card">
            <div class="form-grid">
              <div>
                <label for="authorUrl">单条主页链接（支持抖音 / 小红书；留空用已勾选第一条）</label>
                <input id="authorUrl" type="url" placeholder="https://www.douyin.com/user/… 或 https://www.xiaohongshu.com/user/profile/…">
              </div>
              <div style="display:flex;gap:8px;align-items:end">
                <div style="flex:1"><label for="auBatchInput">批量添加到当前分组（粘贴多个主页地址）</label><input id="auBatchInput" type="text" placeholder="输入主页链接，点右侧保存进当前分组"></div>
                <button class="secondary" type="button" style="height:38px" onclick="auAddFromInput()">添加主页</button>
              </div>
            </div>
            <div class="param-chips">
              <div class="param-chip"><span>每主页数量</span><input type="number" id="a_max_per_author" min="1" max="150" value="10"></div>
              <div class="param-chip"><span>图文张数</span><input type="number" id="a_min_images" min="0" max="50" value="0"><span>至</span><input type="number" id="a_max_images" min="0" max="50" value="50"><span>张</span></div>
              <label class="param-chip" style="cursor:pointer"><input type="checkbox" id="a_direct_download" style="width:15px;height:15px;margin:0;accent-color:var(--accent)"> 同时下载素材</label>
            </div>
            <div class="btn-row" style="margin-top:0">
              <button class="primary" id="startHomepage" type="button">采集主页</button>
            </div>
            <p class="panel-sub" id="homepageCapability" style="margin:0">正在检测内置 Edge 采集核心…</p>
            <div class="collection-status" id="homepageStatus" role="status" hidden style="margin:0"></div>
          </div>

          <div class="toolbar" style="margin-top:14px">
            <select class="sort-select group-select" id="auGroupFilter" data-filtered="false" onchange="onAuGroupChange(this.value)" title="按分组筛选"><option value="all">全部分组</option></select>
            <button class="mini-btn" type="button" onclick="openGroupManager('authors')" title="新建、重命名或删除主页分组">分组管理</button>
            <button class="mini-btn" type="button" onclick="auBatch('all')">全选本组</button>
            <button class="mini-btn" type="button" onclick="auBatch('invert')">反选</button>
            <button class="mini-btn" type="button" onclick="auBatch('none')">清空</button>
            <input class="search-box" type="text" id="auSearch" placeholder="搜索作者/分组/备注…" oninput="refreshAuthors()">
            <select class="sort-select" id="auSortBy" onchange="refreshAuthors()"><option value="seq">按序号</option><option value="name">按作者名</option><option value="fans">按粉丝量</option><option value="works">按作品数</option><option value="publish_time">按最近发布</option><option value="group">按分组</option></select>
            <button class="mini-btn" id="auSortDirBtn" type="button" onclick="toggleAuSortDir()" title="切换升序/降序">↑ 升序</button>
            <input type="file" id="auFileInput" accept=".txt,.csv" hidden onchange="auImportFile(this)">
            <button class="mini-btn" type="button" onclick="$('auFileInput').click()">导入主页(.txt)</button>
            <button class="mini-btn" type="button" onclick="auMetaPrompt()">改分组/备注</button>
            <button class="mini-btn danger" type="button" onclick="auDeleteSelected()">删除选中</button>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead><tr><th>选择</th><th>序号</th><th>平台</th><th>分组</th><th>作者</th><th>网址</th><th>粉丝</th><th>作品</th><th>备注</th><th>操作</th></tr></thead>
              <tbody id="auTableBody"><tr><td colspan="10" style="text-align:center;color:var(--muted)">暂无保存的作者主页，可在上方粘贴添加或直接提取。</td></tr></tbody>
            </table>
          </div>
        </section>

        <!-- 4. 作品列表（统一资产库） -->
        <section class="surface work-panel" id="artworksPanel" role="tabpanel" hidden>
          <div class="eyebrow">Unified Artwork Library</div>
          <div class="panel-head-row">
            <div><h2>作品列表与统一历史记录</h2><p class="lead">汇总当前采集结果、剪贴板采集、AI 任务与历史档案，支持读取时间排序、多维度筛选及一键下载入库。</p></div>
            <div class="seg-group" id="artViewSeg">
              <button class="seg-btn active" type="button" data-mode="current">当前采集列表</button>
              <button class="seg-btn" type="button" data-mode="history">历史采集列表</button>
            </div>
          </div>

          <div class="toolbar">
            <input class="search-box" type="text" id="artSearch" placeholder="按标题、关键词、作者搜索…" oninput="refreshArtworks()">
            <select id="artTypeFilter" style="width:105px;height:34px" onchange="refreshArtworks()"><option value="all">全部类型</option><option value="图文">仅图文</option><option value="视频">仅视频</option><option value="AI任务">AI任务</option></select>
            <select id="artStatusFilter" style="width:132px;height:34px" onchange="refreshArtworks()"><option value="all">全部状态</option><option value="problem">失败/待补/未知</option><option value="done">已下载成功</option><option value="pending">待补素材</option><option value="blocked">规则拦截</option><option value="unknown">结果未知/部分失败</option></select>
            <select id="artSortBy" style="width:120px;height:34px" onchange="refreshArtworks()"><option value="collected_at" selected>按读取时间</option><option value="seq">默认序号</option><option value="likes">按点赞量</option><option value="favorites">按收藏量</option><option value="comments">按评论量</option><option value="image_count">按图片数</option><option value="publish_time">按发布时间</option></select>
            <button class="mini-btn" type="button" onclick="artBatch('all')">全选</button>
            <button class="mini-btn" type="button" onclick="artBatch('invert')">反选</button>
            <button class="mini-btn" type="button" onclick="artBatch('none')">清空</button>
            <button class="mini-btn" type="button" onclick="artResetFilters()">重置筛选</button>
            <button class="mini-btn" id="retryProblemBtn" type="button" onclick="retryProblemArtworks()">重试全部异常项</button>
            <button class="mini-btn" id="artRefreshBtn" type="button">刷新列表</button>
            <button class="mini-btn" type="button" onclick="artExportCsv()">导出 CSV</button>
            <button class="mini-btn danger" type="button" onclick="artDeleteSelected()">删除</button>
          </div>

          <details class="drawer" id="queueDrawer" style="margin-top:8px">
            <summary><span>剪贴板与实时排队任务</span><span class="badge" id="waitingCount" style="margin-left:auto;margin-right:8px">0</span></summary>
            <div class="drawer-body">
              <div class="panel-sub" id="queueSub" style="margin:0">读取剪贴板实时队列与本地下载队</div>
              <div class="scroll-list" id="queueList" style="max-height:160px;margin-top:4px"><div class="panel-sub">暂无排队或剪贴板待处理任务</div></div>
            </div>
          </details>

          <details class="drawer">
            <summary>多条件高级筛选与数值对比规则</summary>
            <div class="drawer-body">
              <div class="form-grid">
                <div><label for="artIncludeKw">标题包含关键字（逗号分隔）</label><input type="text" id="artIncludeKw" placeholder="例如：团建,民宿"></div>
                <div><label for="artExcludeKw">标题排除关键字（逗号分隔）</label><input type="text" id="artExcludeKw" placeholder="例如：广告,抽奖"></div>
              </div>
              <div class="num-row">
                <span>点赞 ≥</span><input type="number" id="artMinLikes" min="0" value="0">
                <span>收藏 ≥</span><input type="number" id="artMinFavorites" min="0" value="0">
                <span>评论 ≥</span><input type="number" id="artMinComments" min="0" value="0">
                <span>图片数 ≥</span><input type="number" id="artMinImages" min="0" value="0">
                <button class="mini-btn" type="button" onclick="refreshArtworks()">应用筛选条件</button>
              </div>
            </div>
          </details>

          <div class="progress-meta" style="margin:10px 0 8px"><span id="artSummaryText">当前 0 条 · 历史 0 条 · 显示 0 条</span></div>
          <div class="table-wrap" style="max-height:calc(100vh - 280px)">
            <table class="data-table">
              <thead><tr><th>选择</th><th>序号</th><th>类型</th><th>来源</th><th>关键词 / 采集方式</th><th>作者</th><th>作品标题</th><th>评 / 藏 / 赞</th><th>发布时间</th><th>读取时间</th><th>图数</th><th>状态</th><th>操作</th></tr></thead>
              <tbody id="artTableBody"><tr><td colspan="13" style="text-align:center;color:var(--muted)">正在加载作品列表…</td></tr></tbody>
            </table>
          </div>

          <div class="btn-row">
            <button class="secondary" type="button" onclick="ingestCheckedArtworks()">一键入库选中作品</button>
            <button class="primary" id="downloadCheckedBtn" type="button" onclick="downloadCheckedArtworks()">开始下载选中作品</button>
          </div>
        </section>

        <!-- 5. 平台登录 -->
        <section class="surface work-panel" id="loginPanel" role="tabpanel" hidden>
          <div class="eyebrow">Built-in Browser Session</div>
          <h2>多平台登录态与内置浏览器调度中心</h2>
          <p class="lead">自动识别本机 Edge / Chrome / Chromium 持久化内核（未安装微软 Edge 时自动无缝切换 Chrome 或内置 Chromium）；扫码登录一次永久保存会话，遇到验证码自动居中置顶弹出提醒。</p>
          <div class="login-grid">
            <div class="login-card">
              <strong>抖音桌面会话</strong>
              <span style="font-size:12px;color:var(--muted)" id="loginDyInfo">用于抖音关键词搜索、主页发现与人机验证</span>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <button class="mini-btn" type="button" onclick="engineAction('open_platform_login',{platform:'douyin'})">抖音登录 / 打开窗口</button>
              </div>
            </div>
            <div class="login-card">
              <strong>小红书桌面会话</strong>
              <span style="font-size:12px;color:var(--muted)" id="loginXhsInfo">用于小红书登录态、主页与搜索笔记采集</span>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <button class="mini-btn" type="button" onclick="engineAction('open_platform_login',{platform:'xiaohongshu'})">小红书登录 / 打开窗口</button>
              </div>
            </div>
            <div class="login-card">
              <strong>小红书聚光（内容广场）</strong>
              <span style="font-size:12px;color:var(--muted)" id="loginJuguangInfo">用于聚光内容广场（客资收集 / 近7日 / 阅读量）关键词采集与高潜图文挖掘</span>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <button class="mini-btn" type="button" onclick="engineAction('open_platform_login',{platform:'juguang'})">聚光登录 / 打开内容广场</button>
              </div>
            </div>
            <div class="login-card">
              <strong>浏览器窗口控制</strong>
              <span style="font-size:12px;color:var(--muted)">登录或过完验证码后可一键收起，登录状态永久保留在本机档案中</span>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <button class="mini-btn" type="button" onclick="engineAction('bring_verify_browser',{platform:activeEnginePlatform})">弹出 / 置顶浏览器</button>
                <button class="mini-btn" type="button" onclick="engineAction('hide_browser',{})">收起浏览器</button>
              </div>
            </div>
            <div class="login-card">
              <strong>多账号浏览器档案（防限流一键切换）</strong>
              <span style="font-size:12px;color:var(--muted)">不同档案隔离 Cookie 与指纹会话，高频采集切备用号不串号</span>
              <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                <select id="profileSelect" style="flex:1;min-width:130px;height:34px"><option value="default">默认主账号</option></select>
                <button class="mini-btn" type="button" onclick="switchBrowserProfile()">切换档案</button>
                <button class="mini-btn" type="button" onclick="createBrowserProfile()">新建档案</button>
                <button class="mini-btn danger" type="button" onclick="deleteBrowserProfile()">删除</button>
              </div>
            </div>
            <div class="login-card" style="grid-column:1 / -1">
              <strong>反检测内核与采集规则自检</strong>
              <div id="engineRuleHealthBox" style="font-size:12px;color:var(--muted);line-height:1.6">正在检测内核驱动与接口规则状态…</div>
            </div>
          </div>
          <div class="collection-status" id="loginActionFeedback" hidden></div>
        </section>

        <!-- 7. 下载与软件设置 -->
        <section class="surface work-panel" id="settingsPanel" role="tabpanel" hidden>
          <div class="eyebrow">Download & App Preferences</div>
          <h2>下载设置、归档规则与通知提醒</h2>
          <p class="lead">仅保留 100% 实际生效的下载与工作台配置（路径/去重/自动入库/清晰度/命名/窗口与飞书通知）；视觉主题请直接点击右上角主题菜单。</p>

          <div class="subtabs" id="settingSubTabs">
            <button class="seg-btn active" type="button" data-sub="subPath">路径、去重与自动入库</button>
            <button class="seg-btn" type="button" data-sub="subTitle">格式、节奏与命名模板</button>
            <button class="seg-btn" type="button" data-sub="subTheme">窗口、通知与飞书提醒</button>
            <button class="seg-btn" type="button" data-sub="subAi">AI 接入</button>
          </div>

          <div class="subpanel active" id="subPath">
            <div class="form-grid">
              <div class="wide"><label for="d_output_dir">作品保存根目录</label><div style="display:flex;gap:8px;align-items:center"><input type="text" id="d_output_dir" style="flex:1"><button class="secondary" type="button" style="height:38px" onclick="pickFolderInto('d_output_dir')">浏览选择…</button></div></div>
            </div>
            <div class="check-grid" style="margin-top:12px">
              <label class="check-item"><input type="checkbox" id="d_skip_downloaded_history" checked> 自动跳过已下载过的历史作品（去重）</label>
            </div>
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--line);display:grid;gap:10px">
              <strong style="font-size:12.5px">本地素材自动分类入库（01月~12月平铺硬链接 · 主题合集 · 多维元数据 · 广告滤图）</strong>
              <div class="check-grid">
                <label class="check-item"><input type="checkbox" id="d_auto_ingest_material" checked> 采集下载后自动按本地规则分类入库</label>
                <label class="check-item"><input type="checkbox" id="d_auto_ingest_copy_only" checked> 保留下载目录原件（复制入库，不删原目录）</label>
                <label class="check-item"><input type="checkbox" id="d_write_metadata" checked> 自动生成并更新作品元数据（metadata.json）</label>
              </div>
              <div class="form-grid">
                <div class="wide"><label for="d_auto_ingest_config_path">入库规则配置文件（config.json）</label><div style="display:flex;gap:8px;align-items:center"><input type="text" id="d_auto_ingest_config_path" placeholder="config/config.json" style="flex:1"><button class="secondary" type="button" style="height:38px" onclick="openConfigFileEditor()">打开编辑</button></div></div>
              </div>
            </div>
          </div>

          <div class="subpanel" id="subTitle">
            <div class="form-grid">
              <div><label for="d_image_format">图片保存格式</label><select id="d_image_format"><option value="jpg" selected>JPG（推荐 · 全平台通用无 WebP）</option><option value="png">PNG（无损）</option><option value="keep">保持平台原格式（可能为 WebP）</option></select></div>
              <div><label for="d_delay_mode">下载防频繁节奏</label><select id="d_delay_mode"><option value="auto">智能 · 随结果调节</option><option value="fast">快速 · 3–8 秒</option><option value="normal">标准 · 8–15 秒</option><option value="cautious">稳妥 · 35–55 秒</option><option value="slow">慢速 · 55–85 秒</option><option value="very-slow">极慢 · 110–160 秒</option></select></div>
              <div class="wide"><label for="d_title_template">文件夹命名模板（可点下方占位符拼接 DIY，或手动输入）</label><input type="text" id="d_title_template" value="评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}" oninput="updateTitleTemplatePreview()">
                <div class="btn-row" style="margin-top:6px;gap:6px">
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{comments}')">+评论{comments}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{favorites}')">+收藏{favorites}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{likes}')">+点赞{likes}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{title}')">+标题{title}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{author}')">+作者{author}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{publish_time}')">+发布日期{publish_time}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{keyword}')">+关键词{keyword}</button>
                  <button class="mini-btn" type="button" onclick="insertTemplateToken('{id}')">+ID{id}</button>
                </div>
                <div class="btn-row" style="margin-top:6px;gap:6px">
                  <button class="mini-btn" type="button" onclick="applyTitleTemplatePreset('评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}')">预设：评藏赞+标题+作者+日期</button>
                  <button class="mini-btn" type="button" onclick="applyTitleTemplatePreset('评{comments}-赞{likes}-{title}-{author}-{publish_time}')">预设：评赞+标题+作者+日期</button>
                  <button class="mini-btn" type="button" onclick="applyTitleTemplatePreset('{publish_datetime}_{author}_{title}')">预设：时间_作者_标题</button>
                </div>
                <div class="panel-sub" id="titleTemplatePreview" style="margin-top:6px">预览效果：评12-藏34-赞88-安吉温泉团建攻略-小旅-2026-11-25</div>
              </div>
            </div>
            <div class="check-grid" style="margin-top:12px">
              <label class="check-item"><input type="checkbox" id="d_set_file_time_to_publish" checked> 文件修改时间同步为作品发布时间</label>
            </div>
          </div>

          <div class="subpanel" id="subTheme">
            <div style="display:grid;gap:10px">
              <div class="form-grid">
                <div class="wide"><label for="sw_proxy_url">网络代理地址（可选，留空直接直连；例：http://127.0.0.1:7890）</label><input type="text" id="sw_proxy_url" placeholder="可选：http://127.0.0.1:7890（留空直连）"></div>
              </div>
              <div class="num-row">
                <strong style="font-size:12.5px">自动主题昼夜规则（北京时间）：</strong>
                <span>白天开始</span><input type="number" id="sw_theme_day_start" min="0" max="23" value="7" style="width:66px"><span>点</span>
                <span>夜晚开始</span><input type="number" id="sw_theme_night_start" min="0" max="23" value="19" style="width:66px"><span>点</span>
                <span>质感风格</span><select id="sw_theme_auto_style" style="width:auto;min-width:160px;height:32px"><option value="rotate">按日轮换拟态/玻璃</option><option value="neo">固定拟态质感</option><option value="glass">固定玻璃质感</option><option value="flat">固定纯净质感</option></select>
              </div>
            </div>
            <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--line)">
              <strong style="display:block;font-size:13px;margin-bottom:8px">验证置顶、桌面弹窗与飞书通知</strong>
              <div class="check-grid">
                <label class="check-item"><input type="checkbox" id="sw_auto_topmost_verify_window" checked> 遇到验证码/登录拦截时自动弹出并置顶验证浏览器</label>
                <label class="check-item"><input type="checkbox" id="sw_notify_desktop_toast" checked> 发送电脑桌面气泡通知 + 提示音</label>
                <label class="check-item"><input type="checkbox" id="sw_notify_feishu" checked> 发送飞书群消息通知</label>
                <label class="check-item"><input type="checkbox" id="sw_notify_on_complete" checked> 采集任务结束时也发送完成通知</label>
              </div>
              <div class="btn-row" style="margin-top:10px">
                <button class="mini-btn" type="button" onclick="engineAction('test_notification',{})">测试桌面 + 飞书通知</button>
              </div>
              <details class="drawer" id="feishuConfigDrawer" style="margin-top:10px">
                <summary>飞书机器人连接配置（可选：群 Webhook 或 App ID / 密钥 / 群 ID）</summary>
                <div class="drawer-body">
                  <div class="form-grid">
                    <div><label for="sw_notify_feishu_app_id">机器人 App ID（企业自建应用）</label><input type="text" id="sw_notify_feishu_app_id" placeholder="可选：cli_xxxxxxxxxx"></div>
                    <div><label for="sw_notify_feishu_app_secret">机器人 App Secret（密钥）</label><input type="password" id="sw_notify_feishu_app_secret" placeholder="可选：应用密钥" autocomplete="off"></div>
                    <div><label for="sw_notify_feishu_target">飞书群名称或群 ID（oc_xxx）</label><input type="text" id="sw_notify_feishu_target" value="素材采集通知群" placeholder="例如：素材采集通知群 或 oc_xxx"></div>
                    <div><label for="sw_notify_feishu_webhook">或：飞书群自定义机器人 Webhook（免建企业应用）</label><input type="url" id="sw_notify_feishu_webhook" placeholder="可选：https://open.feishu.cn/open-apis/bot/v2/hook/..."></div>
                  </div>
                  <p class="panel-sub" style="margin:0">提示：个人用户只需在飞书群添加「自定义机器人」并粘贴 Webhook 地址即可（免建企业应用）；团队用户可填写 App ID + 密钥 + 群 ID/群名称；均留空则自动沿用本机默认配置。</p>
                </div>
              </details>
            </div>
            <details class="drawer" style="margin-top:10px">
              <summary>高级维护与旧版档案迁移</summary>
              <div class="drawer-body">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
                  <span style="font-size:12px;color:var(--muted)">旧版历史档案迁移：如曾使用旧采集器积累了词表与作品档案，可在此手工导入合并</span>
                  <button class="mini-btn" type="button" onclick="migrateLegacyArchive()">导入旧版历史词库与档案</button>
                </div>
              </div>
            </details>
          </div>

          <div class="subpanel" id="subAi">
            <div style="display:grid;gap:12px">
              <div class="quick-launch-card" style="margin:0;display:grid;gap:10px">
                <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap">
                  <div>
                    <strong style="font-size:13.5px">AI Agent 一键接入提示词</strong>
                    <div style="font-size:12px;color:var(--muted);margin-top:2px">复制下方完整指令发给任意 AI Agent（Antigravity / Codex / Claude / Cursor 等），即可记住本机采集器并自动帮你采集下载，无需再配其它规则。</div>
                  </div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <button class="primary" type="button" style="height:36px;padding:0 16px" onclick="copyAiSnippet('aiMasterPrompt')">一键复制给 AI Agent</button>
                    <a class="mini-btn" href="/api/openapi.json" target="_blank" rel="noreferrer" style="text-decoration:none;height:36px;display:inline-flex;align-items:center">查看 OpenAPI 文档</a>
                  </div>
                </div>
                <pre id="aiMasterPrompt" style="margin:0;padding:12px 14px;border-radius:12px;background:var(--input);border:1px solid var(--line);font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word">我的电脑本机运行着「万能下载器 / 万能采集器」桌面应用（本地接口：http://127.0.0.1:5678，仅本机回环访问，无需 API Key）。

从现在开始，凡是我发给你的小红书、抖音（以及 B 站、快手、X、YouTube 等）作品链接、分享文案、关键词找图文/视频需求或作者主页批量采集任务，请一律直接调用这个本地软件的 HTTP 接口来完成采集、无水印下载与分类入库，不要自己手写爬虫去网页扒图：

1. 状态检查：GET http://127.0.0.1:5678/api/v1/health
2. 单作品 / 批量链接解析下载：POST http://127.0.0.1:5678/api/jobs
   Body JSON：{"text": "直接粘贴整段分享文案或一行一条多个链接"}
3. 关键词搜索采集并下载：POST http://127.0.0.1:5678/api/v1/collections/keyword
   Body JSON：{"platform": "douyin" | "xiaohongshu", "keyword": "搜索关键词", "count": 10, "media_type": "image" | "video" | "all", "direct_download": true}
4. 作者主页批量采集：POST http://127.0.0.1:5678/api/v1/collections/homepage
   Body JSON：{"profile_url": "作者主页链接", "max_works": 10, "direct_download": true}
5. 查询任务与历史记录：GET http://127.0.0.1:5678/api/v1/jobs、GET http://127.0.0.1:5678/api/v1/workbench/artworks?mode=history&sort_by=collected_at&sort_dir=desc
（全部参数与接口说明见 OpenAPI：GET http://127.0.0.1:5678/api/openapi.json）

如返回 verification_required / 需要登录，说明平台触发了风控验证，本机软件会自动弹出并置顶浏览器窗口；请提示我完成滑块/扫码验证后继续采集，任务结束后再向我汇总保存路径与成功/跳过数量。</pre>
              </div>
            </div>
          </div>

          <div class="btn-row">
            <button class="primary" type="button" onclick="saveAllWorkbenchSettings(true)">保存全部设置到本地档案</button>
          </div>
        </section>
      </div>
    </section>
  </div>
  <p class="footnote">__APP_NAME__ V__APP_VERSION__ · 统一拟态 / 悬浮玻璃桌面工作台 · 本地闭环运行不泄露账号态</p>
</main>

<dialog class="settings-dialog" id="inputModal" aria-labelledby="inputModalTitle">
  <div class="dialog-heading">
    <div><p id="inputModalSub">分组与备注管理</p><h2 id="inputModalTitle">重命名分组</h2></div>
    <button class="dialog-close" id="inputModalClose" type="button" aria-label="关闭弹窗">×</button>
  </div>
  <div style="display:grid;gap:12px">
    <div id="inputModalSelectWrap" hidden><label id="inputModalSelectLabel" for="inputModalSelect">选择要操作的分组</label><select id="inputModalSelect"></select></div>
    <div><label id="inputModalValueLabel" for="inputModalValue">新名称</label><input id="inputModalValue" type="text" autocomplete="off"></div>
    <div id="inputModalRemarkWrap" hidden><label id="inputModalRemarkLabel" for="inputModalRemark">备注（留空不改）</label><input id="inputModalRemark" type="text" autocomplete="off"></div>
  </div>
  <div class="btn-row">
    <button class="secondary" id="inputModalCancel" type="button" style="height:40px">取消</button>
    <button class="primary" id="inputModalConfirm" type="button" style="height:40px">确认保存</button>
  </div>
</dialog>
<dialog class="settings-dialog" id="groupManagerModal" aria-labelledby="gmTitle" style="width:min(540px,calc(100vw - 32px))">
  <div class="dialog-heading">
    <div><p id="gmSub">新增 / 改名 / 删除分组</p><h2 id="gmTitle">分组管理 DIY</h2></div>
    <button class="dialog-close" type="button" onclick="$('groupManagerModal').close()" aria-label="关闭分组管理">×</button>
  </div>
  <div style="display:grid;gap:12px">
    <div style="display:flex;gap:8px;align-items:center">
      <input id="gmNewName" type="text" placeholder="输入要新建的分组名称…" autocomplete="off" style="flex:1" onkeydown="if(event.key==='Enter'){event.preventDefault();gmCreateGroup();}">
      <button class="primary" type="button" style="flex:0 0 auto;min-width:110px;height:38px;padding:0 14px" onclick="gmCreateGroup()">+ 新建分组</button>
    </div>
    <div class="scroll-list" id="gmList" style="max-height:280px;margin-top:0"><div class="panel-sub">加载中…</div></div>
    <p class="panel-sub" style="margin:0">提示：「仅删组」会把组内条目自动移回「默认分组」；连续点两次「删组含词」可连同组内条目一并移除。</p>
  </div>
</dialog>
<dialog class="settings-dialog" id="rowEditModal" aria-labelledby="reTitle">
  <div class="dialog-heading">
    <div><p id="reSub">单条档案 DIY 编辑</p><h2 id="reTitle">编辑记录</h2></div>
    <button class="dialog-close" type="button" onclick="$('rowEditModal').close()" aria-label="关闭编辑">×</button>
  </div>
  <datalist id="groupDatalist"></datalist>
  <div style="display:grid;gap:12px">
    <div><label id="rePrimaryLabel" for="rePrimary">关键词</label><input id="rePrimary" type="text" autocomplete="off"></div>
    <div id="reUrlWrap" hidden><label for="reUrl">主页网址</label><input id="reUrl" type="url" autocomplete="off"></div>
    <div><label for="reGroup">所属分组（可选现有或直接输入新分组）</label><input id="reGroup" type="text" list="groupDatalist" autocomplete="off"></div>
    <div><label for="reRemark">备注</label><input id="reRemark" type="text" autocomplete="off"></div>
  </div>
  <div class="btn-row">
    <button class="secondary" type="button" style="height:40px" onclick="$('rowEditModal').close()">取消</button>
    <button class="primary" type="button" style="height:40px" onclick="saveRowEdit()">保存修改</button>
  </div>
</dialog>
<div id="wbToast" class="toast" aria-live="polite"></div>

<script>
const THEME_KEY='xhs-dl-theme',THEME_VER_KEY='xhs-dl-theme-v2',OUTPUT_KEY='xhs-dl-output',MODE_KEY='xhs-dl-mode',FORMAT_KEY='xhs-dl-format',DEFAULT_OUTPUT=__DEFAULT_OUTPUT_JSON__,DOWNLOAD_JOB_KEY='xhs-dl-active-download-job';
const CSS_THEMES=['light','dark','neo','neo-dark','glass','glass-dark'];
const THEME_MODES=['auto',...CSS_THEMES];
const CYCLE_THEMES=['auto','neo','neo-dark','glass','glass-dark'];
const THEME_LABELS={'light':'浅色','dark':'深色','neo':'浅色拟态','neo-dark':'深色拟态','glass':'浅色玻璃','glass-dark':'深色玻璃'};
let currentThemeMode='auto';
const $=id=>document.getElementById(id);
let activeJob=null,pollTimer=null,historyItems=[],historyOffset=0,historyTotal=0,collectorEnabled=true,collectorOnline=false;
let wbKeywords=[],wbAuthors=[],wbArtworks=[],wbSettings={},activeKwPlatform='douyin',activeAuPlatform='douyin',activeArtView='current';
let activeKwGroup='all',activeAuGroup='all',kwSortDir='asc',auSortDir='asc',kwGroups=[],auGroups=[],kwBatchQueueStop=false,activeKeywordRun=false;
let collectionPollTimers={homepage:null,keyword:null},toastTimer=null,autoSaveTimer=null;
let activeEnginePlatform='douyin',lastVerifyKey='',lastKwCounter='';

function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
function platLabel(p){return p==='juguang'?'小红书聚光':(p==='xiaohongshu'?'小红书':'抖音');}
function platBadgeClass(p){return p==='juguang'?'jg':(p==='xiaohongshu'?'xhs':'dy');}
function showToast(msg,isErr=false){
  const el=$('wbToast');if(!el||!msg)return;
  el.textContent=msg;el.classList.toggle('err',!!isErr);el.classList.add('show');
  if(toastTimer)clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>el.classList.remove('show'),3400);
}
async function api(url,method='GET',body=null,headers={}){
  const opts={method,headers:{...headers}};
  if(body!==null){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
  const res=await fetch(url,opts);
  const data=await res.json().catch(()=>({}));
  if(!res.ok)throw Object.assign(new Error(data.error||('请求失败: '+res.status)),{status:res.status});
  return data;
}

function resolveAutoTheme(now=new Date()){
  const sw=(wbSettings&&wbSettings.software)||{};
  const dsRaw=Number(sw.theme_day_start);
  const nsRaw=Number(sw.theme_night_start);
  const dayStart=Number.isFinite(dsRaw)?Math.max(0,Math.min(23,Math.trunc(dsRaw))):7;
  const nightStart=Number.isFinite(nsRaw)?Math.max(0,Math.min(23,Math.trunc(nsRaw))):19;
  const style=String(sw.theme_auto_style||'rotate');
  const bjMs=now.getTime()+now.getTimezoneOffset()*60000+8*3600000;
  const bj=new Date(bjMs);
  const hour=bj.getUTCHours();
  const isDay=dayStart<nightStart?(hour>=dayStart&&hour<nightStart):(dayStart>nightStart?(hour>=dayStart||hour<nightStart):(hour>=7&&hour<19));
  if(style==='flat')return isDay?'light':'dark';
  if(style==='neo')return isDay?'neo':'neo-dark';
  if(style==='glass')return isDay?'glass':'glass-dark';
  const dayIdx=Math.floor(bjMs/86400000);
  const useGlass=(dayIdx%2)===0;
  return useGlass?(isDay?'glass':'glass-dark'):(isDay?'neo':'neo-dark');
}
function applyTheme(mode,persist=true){
  const nextMode=THEME_MODES.includes(mode)?mode:'auto';
  currentThemeMode=nextMode;
  const resolved=nextMode==='auto'?resolveAutoTheme():nextMode;
  document.body.dataset.theme=resolved;
  try{localStorage.setItem(THEME_KEY,nextMode);localStorage.setItem(THEME_VER_KEY,'2');}catch(_){}
  const baseLabel=THEME_LABELS[resolved]||'浅色拟态';
  const btn=$('themeButton');
  if(btn){
    if(nextMode==='auto'){
      btn.textContent='主题：自动切换';
      btn.title='自动切换（当前生效：'+baseLabel+'；点击切换下一主题）';
    }else{
      btn.textContent='主题：'+baseLabel;
      btn.title='点击切换下一主题（自动切换 / 浅色拟态 / 深色拟态 / 浅色玻璃 / 深色玻璃）';
    }
  }
  if(persist){
    if(!wbSettings.software)wbSettings.software={};
    wbSettings.software.theme=nextMode;
    api('/api/v1/workbench/settings','POST',{software:{theme:nextMode}}).catch(()=>{});
  }
}
(function initInitialTheme(){
  let savedMode='auto';
  try{
    const ver=localStorage.getItem(THEME_VER_KEY);
    const raw=localStorage.getItem(THEME_KEY);
    savedMode=(ver==='2'&&raw&&THEME_MODES.includes(raw))?raw:'auto';
  }catch(_){}
  applyTheme(savedMode,false);
  setInterval(()=>{if(currentThemeMode==='auto')applyTheme('auto',false);},60000);
})();
$('themeButton').addEventListener('click',()=>{
  const idx=CYCLE_THEMES.indexOf(currentThemeMode);
  const next=CYCLE_THEMES[(idx+1+CYCLE_THEMES.length)%CYCLE_THEMES.length];
  applyTheme(next,true);
});
document.addEventListener('click',e=>{
  document.querySelectorAll('details.more-menu[open]').forEach(m=>{if(!m.contains(e.target))m.removeAttribute('open');});
});

function getOutputDir(){return (($('d_output_dir')&&$('d_output_dir').value)||localStorage.getItem(OUTPUT_KEY)||DEFAULT_OUTPUT).trim()||DEFAULT_OUTPUT;}
if($('d_output_dir'))$('d_output_dir').value=localStorage.getItem(OUTPUT_KEY)||DEFAULT_OUTPUT;
if($('d_delay_mode'))$('d_delay_mode').value=localStorage.getItem(MODE_KEY)||'auto';
if($('d_image_format'))$('d_image_format').value=localStorage.getItem(FORMAT_KEY)||'jpg';

// Liquid sliding nav pill
function moveNavPill(tabEl){
  const pill=$('navLiquidPill');
  if(!pill||!tabEl)return;
  pill.style.opacity='1';
  pill.style.height=tabEl.offsetHeight+'px';
  pill.style.transform=`translate3d(0,${tabEl.offsetTop}px,0)`;
}
function activateNavTab(tabId){
  const tabs=Array.from(document.querySelectorAll('.nav-item'));
  tabs.forEach(btn=>{
    const sel=btn.id===tabId;
    btn.setAttribute('aria-selected',sel?'true':'false');
    const panel=$(btn.dataset.panel);
    if(panel){panel.hidden=!sel;panel.classList.toggle('active',sel);}
    if(sel)requestAnimationFrame(()=>moveNavPill(btn));
  });
  try{localStorage.setItem('xhs-dl-active-tab',tabId);}catch(_){}
  if(tabId==='tabArtworks')refreshArtworks();
}
document.querySelectorAll('.nav-item').forEach(btn=>btn.addEventListener('click',()=>activateNavTab(btn.id)));
window.addEventListener('resize',()=>{const cur=document.querySelector('.nav-item[aria-selected="true"]');if(cur)moveNavPill(cur);});
requestAnimationFrame(()=>moveNavPill($('tabKeyword')));

// Sub-tabs & segmented toggles
document.querySelectorAll('#settingSubTabs .seg-btn').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('#settingSubTabs .seg-btn').forEach(b=>b.classList.toggle('active',b===btn));
  document.querySelectorAll('#settingsPanel .subpanel').forEach(p=>p.classList.toggle('active',p.id===btn.dataset.sub));
}));
document.querySelectorAll('#kwPlatformSeg .seg-btn').forEach(btn=>btn.addEventListener('click',()=>{
  activeKwPlatform=btn.dataset.plat;activeKwGroup='all';
  document.querySelectorAll('#kwPlatformSeg .seg-btn').forEach(b=>b.classList.toggle('active',b===btn));
  syncKwPlatformUi();
  refreshKeywords();
}));
document.querySelectorAll('#auPlatformSeg .seg-btn').forEach(btn=>btn.addEventListener('click',()=>{
  activeAuPlatform=btn.dataset.plat;activeAuGroup='all';
  document.querySelectorAll('#auPlatformSeg .seg-btn').forEach(b=>b.classList.toggle('active',b===btn));
  refreshAuthors();
}));
document.querySelectorAll('#artViewSeg .seg-btn').forEach(btn=>btn.addEventListener('click',()=>{
  activeArtView=btn.dataset.mode;
  document.querySelectorAll('#artViewSeg .seg-btn').forEach(b=>b.classList.toggle('active',b===btn));
  refreshArtworks();
}));

function openArtworkView(mode){
  activeArtView=mode;
  document.querySelectorAll('#artViewSeg .seg-btn').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
  activateNavTab('tabArtworks');
}

function syncKwPlatformUi(){
  const isJg=activeKwPlatform==='juguang';
  ['kwStdSortChip','kwStdTimeChip'].forEach(id=>{if($(id))$(id).style.display=isJg?'none':'';});
  ['kwJuguangCatChip','kwJuguangTimeChip','kwJuguangSortChip'].forEach(id=>{if($(id))$(id).style.display=isJg?'':'none';});
  const inp=$('keywordValue');
  if(inp){
    inp.placeholder=isJg
      ?'输入聚光搜索关键词（如：江浙沪团建，按上方分类 / 近7日 / 阅读量采集）；或勾选词表排队'
      :'输入单个关键词直接开跑；或勾选下方表格多词自动排队';
  }
}

function syncMediaTypeUi(){
  const mtype=($('k_media_type')&&$('k_media_type').value)||'image';
  const chip=$('kwImgRangeChip');
  if(chip){
    const isVid=mtype==='video';
    chip.style.opacity=isVid?'0.48':'1';
    chip.title=isVid?'仅对图文作品生效':'';
  }
}

// Workbench settings load/save
function bindSettingFields(s){
  if(!s)return;wbSettings=s;
  const setVal=(id,val)=>{const el=$(id);if(!el)return;if(el.type==='checkbox')el.checked=!!val;else if(val!=null)el.value=val;};
  const sg=s.single||{},kw=s.keyword||{},au=s.author||{},dl=s.download||{},sw=s.software||{};
  Object.keys(sg).forEach(k=>setVal('s_'+k,sg[k]));
  Object.keys(kw).forEach(k=>{
    if(k==='max_per_keyword')setVal('keywordCount',kw[k]);
    else if(k==='min_images')setVal('minImages',kw[k]);
    else if(k==='max_images')setVal('maxImages',kw[k]);
    else setVal('k_'+k,kw[k]);
  });
  setVal('k_juguang_category',kw.juguang_category||'客资收集');
  setVal('k_juguang_time',kw.juguang_time||'近7日');
  setVal('k_juguang_sort',kw.juguang_sort||'阅读量');
  const mtype=(kw.media_type&&['image','video','all'].includes(kw.media_type))?kw.media_type:(kw.type_video?'all':'image');
  setVal('k_media_type',mtype);
  syncMediaTypeUi();
  syncKwPlatformUi();
  Object.keys(au).forEach(k=>{
    if(k==='mode'){document.querySelectorAll('input[name="a_mode"]').forEach(r=>r.checked=r.value===au[k]);}
    else if(k!=='direct_download')setVal('a_'+k,au[k]);
  });
  Object.keys(dl).forEach(k=>setVal('d_'+k,dl[k]));
  if(dl.auto_ingest_material!=null){
    if($('k_auto_ingest_chip'))$('k_auto_ingest_chip').checked=!!dl.auto_ingest_material;
  }
  if(dl.skip_downloaded_history!=null&&$('k_skip_dup_chip'))$('k_skip_dup_chip').checked=!!dl.skip_downloaded_history;
  setVal('sw_app_window_mode',sw.app_window_mode);
  setVal('sw_minimize_to_tray',sw.minimize_to_tray);
  setVal('sw_auto_topmost_verify_window',sw.auto_topmost_verify_window!=null?sw.auto_topmost_verify_window:true);
  setVal('sw_notify_desktop_toast',sw.notify_desktop_toast!=null?sw.notify_desktop_toast:true);
  setVal('sw_notify_feishu',sw.notify_feishu!=null?sw.notify_feishu:true);
  setVal('sw_notify_on_complete',sw.notify_on_complete!=null?sw.notify_on_complete:true);
  if(sw.notify_feishu_target!=null)setVal('sw_notify_feishu_target',sw.notify_feishu_target);
  if(sw.notify_feishu_app_id!=null)setVal('sw_notify_feishu_app_id',sw.notify_feishu_app_id);
  if(sw.notify_feishu_app_secret!=null)setVal('sw_notify_feishu_app_secret',sw.notify_feishu_app_secret);
  if(sw.notify_feishu_webhook!=null)setVal('sw_notify_feishu_webhook',sw.notify_feishu_webhook);
  if(sw.proxy_url!=null)setVal('sw_proxy_url',sw.proxy_url);
  if(sw.theme_day_start!=null)setVal('sw_theme_day_start',sw.theme_day_start);
  if(sw.theme_night_start!=null)setVal('sw_theme_night_start',sw.theme_night_start);
  if(sw.theme_auto_style!=null)setVal('sw_theme_auto_style',sw.theme_auto_style);
  updateTitleTemplatePreview();
  if(sw.theme&&THEME_MODES.includes(sw.theme)&&localStorage.getItem(THEME_VER_KEY)!=='2')applyTheme(sw.theme,false);
  else if(currentThemeMode==='auto')applyTheme('auto',false);
}

function updateTitleTemplatePreview(){
  const el=$('d_title_template'),out=$('titleTemplatePreview');
  if(!el||!out)return;
  const raw=(el.value||'').trim()||'评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}';
  const sample={'{comments}':'12','{favorites}':'34','{likes}':'88','{title}':'安吉温泉团建攻略','{author}':'小旅','{publish_time}':'2026-11-25','{publish_datetime}':'2026-11-25_14-30','{keyword}':'安吉温泉','{id}':'6738ab12'};
  let rendered=raw;
  Object.keys(sample).forEach(k=>{rendered=rendered.split(k).join(sample[k]);});
  out.textContent='预览效果：'+rendered;
}

function insertTemplateToken(tok){
  const el=$('d_title_template');if(!el||!tok)return;
  const val=el.value||'';
  if(document.activeElement===el&&typeof el.selectionStart==='number'){
    const s=el.selectionStart,e=el.selectionEnd;
    el.value=val.slice(0,s)+tok+val.slice(e);
    el.setSelectionRange(s+tok.length,s+tok.length);
  }else{
    el.value=val?((/[-_/]$/.test(val)?val:val+'-')+tok):tok;
  }
  updateTitleTemplatePreview();
  el.focus();
  saveAllWorkbenchSettings(false);
}

async function pickFolderInto(inputId){
  const el=$(inputId);
  const initial_dir=(el&&el.value||'').trim();
  try{
    const d=await api('/api/v1/workbench/engine','POST',{action:'pick_folder',params:{initial_dir}});
    if(d&&d.path){
      if(el)el.value=d.path;
      await saveAllWorkbenchSettings(true);
    }else if(d&&d.cancelled){
      showToast('已取消目录选择');
    }
  }catch(e){showToast('打开目录选择器失败：'+e.message,true);}
}

async function openConfigFileEditor(){
  const p=($('d_auto_ingest_config_path')&&$('d_auto_ingest_config_path').value||'').trim()||'config/config.json';
  try{
    const d=await api('/api/v1/workbench/engine','POST',{action:'open_file',params:{path:p}});
    showToast((d&&d.message)||'已用系统编辑器打开配置文件');
  }catch(e){showToast('打开配置文件失败：'+e.message,true);}
}

function applyTitleTemplatePreset(tmpl){
  if($('d_title_template'))$('d_title_template').value=tmpl;
  updateTitleTemplatePreview();
  saveAllWorkbenchSettings(false);
  showToast('已切换命名模板并自动保存');
}

function collectSettingsPatch(){
  const gVal=id=>{const el=$(id);return el?(el.type==='checkbox'?el.checked:(el.type==='number'?Number(el.value||0):el.value)):undefined;};
  const mtype=gVal('k_media_type')||'image';
  return {
    single:{...(wbSettings.single||{}),platform:'auto'},
    keyword:{...(wbSettings.keyword||{}),platform:activeKwPlatform,direct_download:gVal('k_direct_download'),media_type:mtype,type_video:mtype!=='image',max_per_keyword:gVal('keywordCount'),min_images:gVal('minImages'),max_images:gVal('maxImages'),web_sort:gVal('k_web_sort')||'综合排序',web_publish_time:gVal('k_web_publish_time')||'不限',juguang_category:gVal('k_juguang_category')||'客资收集',juguang_time:gVal('k_juguang_time')||'近7日',juguang_sort:gVal('k_juguang_sort')||'阅读量'},
    author:{...(wbSettings.author||{}),platform:activeAuPlatform,max_per_author:gVal('a_max_per_author'),min_images:gVal('a_min_images'),max_images:gVal('a_max_images')},
    download:{...(wbSettings.download||{}),output_dir:gVal('d_output_dir')||getOutputDir(),skip_downloaded_history:gVal('d_skip_downloaded_history'),image_format:gVal('d_image_format'),delay_mode:gVal('d_delay_mode'),title_template:gVal('d_title_template'),set_file_time_to_publish:gVal('d_set_file_time_to_publish'),auto_ingest_material:gVal('d_auto_ingest_material'),auto_ingest_copy_only:gVal('d_auto_ingest_copy_only'),write_metadata:gVal('d_write_metadata'),auto_ingest_config_path:gVal('d_auto_ingest_config_path')},
    software:{...(wbSettings.software||{}),theme:currentThemeMode||'auto',auto_topmost_verify_window:gVal('sw_auto_topmost_verify_window'),notify_desktop_toast:gVal('sw_notify_desktop_toast'),notify_feishu:gVal('sw_notify_feishu'),notify_on_complete:gVal('sw_notify_on_complete'),notify_feishu_target:gVal('sw_notify_feishu_target'),notify_feishu_app_id:gVal('sw_notify_feishu_app_id'),notify_feishu_app_secret:gVal('sw_notify_feishu_app_secret'),notify_feishu_webhook:gVal('sw_notify_feishu_webhook'),proxy_url:gVal('sw_proxy_url')||'',theme_day_start:gVal('sw_theme_day_start'),theme_night_start:gVal('sw_theme_night_start'),theme_auto_style:gVal('sw_theme_auto_style')||'rotate'}
  };
}

async function saveAllWorkbenchSettings(notify){
  try{
    const updated=await api('/api/v1/workbench/settings','POST',collectSettingsPatch());
    wbSettings=updated;
    if(updated.download){
      const outDir=updated.download.output_dir||DEFAULT_OUTPUT;
      const delayMode=updated.download.delay_mode||'auto';
      const imgFmt=updated.download.image_format||'jpg';
      if($('d_output_dir'))$('d_output_dir').value=outDir;
      if($('d_delay_mode'))$('d_delay_mode').value=delayMode;
      if($('d_image_format'))$('d_image_format').value=imgFmt;
      if($('k_auto_ingest_chip'))$('k_auto_ingest_chip').checked=!!updated.download.auto_ingest_material;
      if($('k_skip_dup_chip')&&updated.download.skip_downloaded_history!=null)$('k_skip_dup_chip').checked=!!updated.download.skip_downloaded_history;
      localStorage.setItem(OUTPUT_KEY,outDir);
      localStorage.setItem(MODE_KEY,delayMode);
      localStorage.setItem(FORMAT_KEY,imgFmt);
    }
    if(notify)showToast('设置已保存到本机 workbench_hub.json');
  }catch(e){if(notify)showToast('保存设置失败：'+e.message,true);}
}

function renderGroupSelect(selectId,groups,activeGrp){
  const el=$(selectId);if(!el)return;
  const total=(groups||[]).reduce((s,g)=>s+(g.count||0),0);
  const opts=[{name:'all',label:`全部分组 (${total})`},...(groups||[]).map(g=>({name:g.name,label:`${g.name} (${g.count||0})`}))];
  el.innerHTML=opts.map(o=>`<option value="${esc(o.name)}">${esc(o.label)}</option>`).join('');
  el.value=opts.some(o=>o.name===activeGrp)?activeGrp:'all';
  el.dataset.filtered=el.value!=='all'?'true':'false';
}
function onKwGroupChange(val){activeKwGroup=val||'all';refreshKeywords();}
function onAuGroupChange(val){activeAuGroup=val||'all';refreshAuthors();}
function updateStartKeywordLabel(){
  const btn=$('startKeyword');if(!btn||btn.disabled)return;
  const typed=($('keywordValue').value||'').trim();
  const checkedCount=wbKeywords.filter(r=>r.checked).length;
  btn.textContent=(!typed&&checkedCount>1)?`开始批量采集（已选 ${checkedCount} 个词）`:'开始关键词采集';
}
function kwQueryOpts(){
  return {
    filter_platform:activeKwPlatform,
    filter_group:activeKwGroup,
    search:$('kwSearch').value||'',
    sort_by:($('kwSortBy')&&$('kwSortBy').value)||'seq',
    sort_dir:kwSortDir
  };
}
function renderKeywordTable(){
  renderGroupSelect('kwGroupFilter',kwGroups,activeKwGroup);
  const body=$('kwTableBody');
  if(!wbKeywords.length){body.innerHTML='<tr><td colspan="11" style="text-align:center;color:var(--muted)">当前分组暂无关键词，可在下方添加或点击顶部“导入词库”。</td></tr>';updateStartKeywordLabel();return;}
  body.innerHTML=wbKeywords.map(r=>`<tr>
    <td><input type="checkbox" ${r.checked?'checked':''} onchange="kwToggle('${esc(r.id)}',this.checked)"></td>
    <td>${esc(r.seq)}</td>
    <td><span class="badge ${platBadgeClass(r.platform)}">${esc(platLabel(r.platform))}</span></td>
    <td><span class="badge">${esc(r.group||'默认分组')}</span></td>
    <td><strong>${esc(r.keyword)}</strong></td>
    <td><span class="badge ${r.last_extracted==='是'?'ok':''}">${esc(r.last_extracted)}</span></td><td>${esc(r.last_count)}</td><td>${esc(r.recorded_ids)}</td>
    <td>${esc(r.remark)}</td><td class="cell-ellipsis">${esc(r.last_time)}</td>
    <td style="white-space:nowrap"><button class="mini-btn" type="button" onclick="openRowEdit('keywords','${esc(r.id)}')">编辑</button> <button class="mini-btn" type="button" onclick="kwRunSingle('${esc(r.keyword)}')">采集</button></td>
  </tr>`).join('');
  updateStartKeywordLabel();
}
function applyKwPayload(d){wbKeywords=d.items||[];kwGroups=d.groups||[];renderKeywordTable();}
async function refreshKeywords(){
  const q=new URLSearchParams({platform:activeKwPlatform,group:activeKwGroup,search:$('kwSearch').value||'',sort_by:($('kwSortBy')&&$('kwSortBy').value)||'seq',sort_dir:kwSortDir});
  const d=await api('/api/v1/workbench/keywords?'+q.toString());applyKwPayload(d);
}
function toggleKwSortDir(){kwSortDir=kwSortDir==='asc'?'desc':'asc';$('kwSortDirBtn').textContent=kwSortDir==='asc'?'↑ 升序':'↓ 降序';refreshKeywords();}
async function kwToggle(id,checked){const d=await api('/api/v1/workbench/keywords','POST',{op:'toggle',id,checked,...kwQueryOpts()});applyKwPayload(d);}
async function kwBatch(mode){const d=await api('/api/v1/workbench/keywords','POST',{op:'batch_select',mode,platform:activeKwPlatform,group:activeKwGroup,...kwQueryOpts()});applyKwPayload(d);}
async function kwAddFromInput(){
  const t=$('kwBatchInput').value.trim();if(!t)return;
  const targetGroup=(activeKwGroup&&activeKwGroup!=='all')?activeKwGroup:'默认分组';
  const d=await api('/api/v1/workbench/keywords','POST',{op:'add',platform:activeKwPlatform,group:targetGroup,text:t.replace(/[,，\s]+/g,'\n'),...kwQueryOpts()});
  applyKwPayload(d);$('kwBatchInput').value='';showToast(d.message||`已添加到分组「${targetGroup}」`);
}
const inputModal=$('inputModal');
function openInputModal(opts){
  return new Promise(resolve=>{
    $('inputModalSub').textContent=opts.sub||'DIY 编辑';
    $('inputModalTitle').textContent=opts.title||'输入内容';
    $('inputModalValueLabel').textContent=opts.valueLabel||'新名称';
    $('inputModalValue').value=opts.value||'';
    $('inputModalValue').placeholder=opts.placeholder||'';
    const selWrap=$('inputModalSelectWrap'),sel=$('inputModalSelect');
    if(opts.options&&opts.options.length){
      $('inputModalSelectLabel').textContent=opts.selectLabel||'选择分组';
      sel.innerHTML=opts.options.map(o=>`<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('');
      if(opts.selectedValue&&opts.options.some(o=>o.value===opts.selectedValue))sel.value=opts.selectedValue;
      selWrap.hidden=false;
    }else{
      selWrap.hidden=true;sel.innerHTML='';
    }
    const rmWrap=$('inputModalRemarkWrap'),rmEl=$('inputModalRemark');
    if(opts.showRemark){
      $('inputModalRemarkLabel').textContent=opts.remarkLabel||'备注（留空不改）';
      rmEl.value=opts.remarkValue||'';
      rmWrap.hidden=false;
    }else{
      rmWrap.hidden=true;rmEl.value='';
    }
    const cleanup=(ok)=>{
      $('inputModalConfirm').onclick=null;$('inputModalCancel').onclick=null;$('inputModalClose').onclick=null;
      $('inputModalValue').onkeydown=null;
      inputModal.oncancel=null;
      try{if(inputModal.open)inputModal.close();}catch(_){}
      resolve(ok?{select:sel.value,value:$('inputModalValue').value,remark:rmEl.value}:null);
    };
    $('inputModalConfirm').onclick=()=>cleanup(true);
    $('inputModalCancel').onclick=()=>cleanup(false);
    $('inputModalClose').onclick=()=>cleanup(false);
    inputModal.oncancel=e=>{e.preventDefault();cleanup(false);};
    $('inputModalValue').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();cleanup(true);}};
    inputModal.showModal();
    requestAnimationFrame(()=>$('inputModalValue').focus());
  });
}
inputModal.addEventListener('click',e=>{if(e.target===inputModal)$('inputModalCancel').click();});

async function kwAssignGroupPrompt(){
  const def=(activeKwGroup&&activeKwGroup!=='all')?activeKwGroup:'新项目分组';
  const r=await openInputModal({sub:'关键词词表归类',title:'分配选中关键词到分组',valueLabel:'目标分组名称（将应用到当前已勾选的关键词）',value:def,placeholder:'例如：江浙沪秋景'});
  if(!r||!r.value.trim())return;
  const g=r.value.trim();
  try{
    const d=await api('/api/v1/workbench/keywords','POST',{op:'update_group',group:g,...kwQueryOpts()});
    activeKwGroup=g;await refreshKeywords();showToast(d.message);
  }catch(e){showToast(e.message,true);}
}
async function kwRenameGroupPrompt(){
  if(!kwGroups||!kwGroups.length){showToast('当前平台暂无可重命名的分组',true);return;}
  const pre=(activeKwGroup&&activeKwGroup!=='all')?activeKwGroup:kwGroups[0].name;
  const r=await openInputModal({
    sub:'关键词分组 DIY',title:'重命名关键词分组',
    selectLabel:'选择要重命名的原分组',
    options:kwGroups.map(g=>({value:g.name,label:`${g.name} (${g.count||0})`})),
    selectedValue:pre,
    valueLabel:'重命名后的新分组名',value:pre
  });
  if(!r||!r.select||!r.value.trim()||r.value.trim()===r.select)return;
  const newGrp=r.value.trim();
  try{
    const d=await api('/api/v1/workbench/keywords','POST',{op:'rename_group',platform:activeKwPlatform,old_group:r.select,new_group:newGrp,...kwQueryOpts()});
    activeKwGroup=newGrp;await refreshKeywords();showToast(d.message);
  }catch(e){showToast(e.message,true);}
}
async function readTextSmart(file){
  const buf=await file.arrayBuffer();
  try{return new TextDecoder('utf-8',{fatal:true}).decode(buf);}
  catch(_){try{return new TextDecoder('gbk').decode(buf);}catch(__){return await file.text();}}
}
async function kwImportFile(input){
  const file=input.files&&input.files[0];if(!file)return;
  try{
    const text=await readTextSmart(file);
    const stem=file.name.replace(/\.[^.]+$/,'').trim();
    const targetGroup=(activeKwGroup&&activeKwGroup!=='all')?activeKwGroup:(stem||'导入分组');
    const d=await api('/api/v1/workbench/keywords','POST',{op:'add',platform:activeKwPlatform,group:targetGroup,parse_group:true,text,...kwQueryOpts()});
    activeKwGroup=targetGroup;await refreshKeywords();
    showToast(d.message||`已从 ${file.name} 导入到分组「${targetGroup}」`);
  }catch(e){showToast('导入失败：'+e.message,true);}
  finally{input.value='';}
}
async function kwDeleteSelected(){const d=await api('/api/v1/workbench/keywords','POST',{op:'delete',...kwQueryOpts()});applyKwPayload(d);showToast(d.message||'已移除选中关键词');}
async function kwSyncJianghu(){const d=await api('/api/v1/workbench/keywords','POST',{op:'sync_jianghu',...kwQueryOpts()});applyKwPayload(d);}
async function kwImportPreset(){try{const d=await api('/api/v1/workbench/keywords','POST',{op:'import_jzh_preset',platform:activeKwPlatform,...kwQueryOpts()});activeKwGroup='江浙沪补缺';await refreshKeywords();showToast(d.message||'已导入江浙沪46词到「江浙沪补缺」分组');}catch(e){showToast('导入失败：'+e.message,true);}}
async function kwRemarkPrompt(){
  const r=await openInputModal({sub:'关键词备注 DIY',title:'修改选中关键词备注',valueLabel:'新备注内容',value:'默认'});
  if(!r)return;
  const d=await api('/api/v1/workbench/keywords','POST',{op:'update_remark',remark:r.value,...kwQueryOpts()});
  applyKwPayload(d);showToast(d.message||'已更新备注');
}
function kwCopySelected(){const list=wbKeywords.filter(r=>r.checked).map(r=>r.keyword);if(!list.length){showToast('请先勾选至少一个关键词',true);return;}navigator.clipboard&&navigator.clipboard.writeText(list.join('\n'));showToast('已复制 '+list.length+' 个关键词');}
function kwExport(){const list=wbKeywords.map(r=>`${r.group||'默认分组'},${r.keyword}`).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff分组,关键词\n'+list],{type:'text/csv;charset=utf-8'}));a.download='keywords.csv';a.click();}
function kwRunSingle(kw){$('keywordValue').value=kw;submitCollection('keyword');}

// Authors CRUD & rendering
function auQueryOpts(){
  return {
    filter_platform:activeAuPlatform,
    filter_group:activeAuGroup,
    search:$('auSearch').value||'',
    sort_by:($('auSortBy')&&$('auSortBy').value)||'seq',
    sort_dir:auSortDir
  };
}
function renderAuthorTable(){
  renderGroupSelect('auGroupFilter',auGroups,activeAuGroup);
  const body=$('auTableBody');
  if(!wbAuthors.length){body.innerHTML='<tr><td colspan="10" style="text-align:center;color:var(--muted)">当前分组暂无保存的主页作者，可在下方粘贴或点击“导入主页”。</td></tr>';return;}
  body.innerHTML=wbAuthors.map(r=>`<tr>
    <td><input type="checkbox" ${r.checked?'checked':''} onchange="auToggle('${esc(r.id)}',this.checked)"></td>
    <td>${esc(r.seq)}</td>
    <td><span class="badge ${platBadgeClass(r.platform)}">${esc(platLabel(r.platform))}</span></td>
    <td><span class="badge">${esc(r.group||'默认分组')}</span></td><td><strong>${esc(r.name)}</strong></td>
    <td class="cell-ellipsis">${esc(r.url)}</td><td>${esc(r.fans)}</td><td>${esc(r.works_count)}</td><td>${esc(r.remark)}</td>
    <td style="white-space:nowrap"><button class="mini-btn" type="button" onclick="openRowEdit('authors','${esc(r.id)}')">编辑</button> <button class="mini-btn" type="button" onclick="auRunSingle('${esc(r.url)}')">采集</button></td>
  </tr>`).join('');
}
function applyAuPayload(d){wbAuthors=d.items||[];auGroups=d.groups||[];renderAuthorTable();}
async function refreshAuthors(){
  const q=new URLSearchParams({platform:activeAuPlatform,group:activeAuGroup,search:$('auSearch').value||'',sort_by:($('auSortBy')&&$('auSortBy').value)||'seq',sort_dir:auSortDir});
  const d=await api('/api/v1/workbench/authors?'+q.toString());applyAuPayload(d);
}
function toggleAuSortDir(){auSortDir=auSortDir==='asc'?'desc':'asc';$('auSortDirBtn').textContent=auSortDir==='asc'?'↑ 升序':'↓ 降序';refreshAuthors();}
async function auToggle(id,checked){const d=await api('/api/v1/workbench/authors','POST',{op:'toggle',id,checked,...auQueryOpts()});applyAuPayload(d);}
async function auBatch(mode){const d=await api('/api/v1/workbench/authors','POST',{op:'batch_select',mode,platform:activeAuPlatform,group:activeAuGroup,...auQueryOpts()});applyAuPayload(d);}
async function auAddFromInput(){
  const t=$('auBatchInput').value.trim();if(!t)return;
  const targetGroup=(activeAuGroup&&activeAuGroup!=='all')?activeAuGroup:'默认分组';
  const d=await api('/api/v1/workbench/authors','POST',{op:'add',platform:activeAuPlatform,group:targetGroup,text:t,...auQueryOpts()});
  applyAuPayload(d);$('auBatchInput').value='';showToast(d.message||`已添加到分组「${targetGroup}」`);
}
async function auImportFile(input){
  const file=input.files&&input.files[0];if(!file)return;
  try{
    const text=await readTextSmart(file);
    const stem=file.name.replace(/\.[^.]+$/,'').trim();
    const targetGroup=(activeAuGroup&&activeAuGroup!=='all')?activeAuGroup:(stem||'导入主页');
    const d=await api('/api/v1/workbench/authors','POST',{op:'add',platform:activeAuPlatform,group:targetGroup,text,...auQueryOpts()});
    activeAuGroup=targetGroup;await refreshAuthors();showToast(d.message||`已导入到分组「${targetGroup}」`);
  }catch(e){showToast('导入失败：'+e.message,true);}
  finally{input.value='';}
}
async function auDeleteSelected(){const d=await api('/api/v1/workbench/authors','POST',{op:'delete',...auQueryOpts()});applyAuPayload(d);showToast(d.message||'已移除选中主页');}
async function auMetaPrompt(){
  const def=(activeAuGroup&&activeAuGroup!=='all')?activeAuGroup:'默认分组';
  const r=await openInputModal({sub:'主页档案编辑',title:'修改选中主页分组与备注',valueLabel:'新分组名（留空不改）',value:def,showRemark:true,remarkLabel:'新备注（留空不改）',remarkValue:''});
  if(!r)return;
  const g=r.value.trim(),rm=r.remark.trim();
  if(!g&&!rm)return;
  const d=await api('/api/v1/workbench/authors','POST',{op:'update_meta',group:g||null,remark:rm||null,...auQueryOpts()});
  if(g)activeAuGroup=g;
  await refreshAuthors();showToast(d.message||'已更新分组/备注');
}
async function auRenameGroupPrompt(){
  openGroupManager('authors');
}
let gmKind='keywords',reKind='keywords',reRowId='';
function openGroupManager(kind){
  gmKind=kind==='authors'?'authors':'keywords';
  const plat=gmKind==='keywords'?activeKwPlatform:activeAuPlatform;
  $('gmSub').textContent=(gmKind==='keywords'?'关键词词表':'作者主页')+' · '+platLabel(plat);
  $('gmTitle').textContent=gmKind==='keywords'?'关键词分组管理 DIY':'主页分组管理 DIY';
  $('gmNewName').value='';
  renderGroupManager();
  $('groupManagerModal').showModal();
  requestAnimationFrame(()=>$('gmNewName').focus());
}
function renderGroupManager(){
  const groups=gmKind==='keywords'?kwGroups:auGroups;
  const list=$('gmList');
  if(!groups||!groups.length){list.innerHTML='<div class="panel-sub">当前平台暂无分组，请在上方新建分组。</div>';return;}
  list.innerHTML=groups.map(g=>{
    const name=String(g.name||'默认分组');
    const isDef=name==='默认分组';
    return `<div class="task-row" data-gm-row="${esc(name)}">
      <div class="task-main"><span class="task-title">${esc(name)}</span><span class="task-meta">${g.count||0} 条记录</span></div>
      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        <button class="mini-btn" type="button" onclick="gmStartRename('${esc(name)}',this)">改名</button>
        ${isDef?'':`<button class="mini-btn" type="button" onclick="gmDeleteGroup('${esc(name)}',false,this)">仅删组</button>
        <button class="mini-btn" type="button" onclick="gmDeleteGroup('${esc(name)}',true,this)">删组含词</button>`}
      </div>
    </div>`;
  }).join('');
}
function gmStartRename(oldName,btn){
  const row=btn&&btn.closest('[data-gm-row]');
  if(!row)return;
  row.innerHTML=`<input type="text" value="${esc(oldName)}" style="flex:1;height:34px;min-width:140px" onkeydown="if(event.key==='Enter'){event.preventDefault();gmCommitRename('${esc(oldName)}',this.value);}else if(event.key==='Escape'){renderGroupManager();}">
    <div style="display:flex;gap:6px">
      <button class="mini-btn" type="button" onclick="gmCommitRename('${esc(oldName)}',this.closest('[data-gm-row]').querySelector('input').value)">保存</button>
      <button class="mini-btn" type="button" onclick="renderGroupManager()">取消</button>
    </div>`;
  const inp=row.querySelector('input');
  if(inp){inp.focus();inp.select();}
}
async function gmCommitRename(oldName,newVal){
  const newGrp=(newVal||'').trim();
  if(!newGrp||newGrp===oldName){renderGroupManager();return;}
  const plat=gmKind==='keywords'?activeKwPlatform:activeAuPlatform;
  const q=gmKind==='keywords'?kwQueryOpts():auQueryOpts();
  try{
    const d=await api('/api/v1/workbench/'+gmKind,'POST',{op:'rename_group',platform:plat,old_group:oldName,new_group:newGrp,...q});
    if(gmKind==='keywords'){if(activeKwGroup===oldName)activeKwGroup=newGrp;applyKwPayload(d);await refreshKeywords();}
    else{if(activeAuGroup===oldName)activeAuGroup=newGrp;applyAuPayload(d);await refreshAuthors();}
    renderGroupManager();
    showToast(d.message||`已重命名为「${newGrp}」`);
  }catch(e){showToast(e.message,true);}
}
async function gmCreateGroup(){
  const name=($('gmNewName').value||'').trim();
  if(!name){showToast('请先输入分组名称',true);$('gmNewName').focus();return;}
  const plat=gmKind==='keywords'?activeKwPlatform:activeAuPlatform;
  const q=gmKind==='keywords'?kwQueryOpts():auQueryOpts();
  try{
    const d=await api('/api/v1/workbench/'+gmKind,'POST',{op:'create_group',platform:plat,group:name,...q});
    $('gmNewName').value='';
    if(gmKind==='keywords'){activeKwGroup=name;applyKwPayload(d);await refreshKeywords();}
    else{activeAuGroup=name;applyAuPayload(d);await refreshAuthors();}
    renderGroupManager();
    showToast(d.message||`已创建分组「${name}」`);
  }catch(e){showToast(e.message,true);}
}
async function gmDeleteGroup(name,deleteItems,btn){
  if(deleteItems&&btn&&btn.dataset.armed!=='1'){
    btn.dataset.armed='1';btn.textContent='确认删除?';btn.style.color='var(--danger)';
    setTimeout(()=>{if(btn.isConnected){btn.dataset.armed='';btn.textContent='删组含词';btn.style.color='';}},3200);
    return;
  }
  const plat=gmKind==='keywords'?activeKwPlatform:activeAuPlatform;
  const q=gmKind==='keywords'?kwQueryOpts():auQueryOpts();
  try{
    const d=await api('/api/v1/workbench/'+gmKind,'POST',{op:'delete_group',platform:plat,group:name,delete_items:!!deleteItems,...q});
    if(gmKind==='keywords'){if(activeKwGroup===name)activeKwGroup='all';applyKwPayload(d);await refreshKeywords();}
    else{if(activeAuGroup===name)activeAuGroup='all';applyAuPayload(d);await refreshAuthors();}
    renderGroupManager();
    showToast(d.message||`已删除分组「${name}」`);
  }catch(e){showToast(e.message,true);}
}
function openRowEdit(kind,id){
  reKind=kind==='authors'?'authors':'keywords';
  reRowId=String(id||'');
  const rows=reKind==='keywords'?wbKeywords:wbAuthors;
  const groups=reKind==='keywords'?kwGroups:auGroups;
  const r=rows.find(x=>String(x.id)===reRowId);
  if(!r){showToast('未找到该条记录',true);return;}
  const dl=$('groupDatalist');
  if(dl)dl.innerHTML=[...new Set(['默认分组',...(groups||[]).map(g=>g.name)])].map(g=>`<option value="${esc(g)}">`).join('');
  if(reKind==='keywords'){
    $('reSub').textContent='关键词档案 DIY 编辑';
    $('reTitle').textContent='编辑关键词';
    $('rePrimaryLabel').textContent='关键词内容';
    $('rePrimary').value=r.keyword||'';
    $('reUrlWrap').hidden=true;
    $('reUrl').value='';
  }else{
    $('reSub').textContent='作者主页 DIY 编辑';
    $('reTitle').textContent='编辑作者主页';
    $('rePrimaryLabel').textContent='作者名称';
    $('rePrimary').value=r.name||'';
    $('reUrlWrap').hidden=false;
    $('reUrl').value=r.url||'';
  }
  $('reGroup').value=r.group||'默认分组';
  $('reRemark').value=r.remark||'';
  $('rowEditModal').showModal();
  requestAnimationFrame(()=>$('rePrimary').focus());
}
async function saveRowEdit(){
  const primary=($('rePrimary').value||'').trim();
  const group=($('reGroup').value||'').trim()||'默认分组';
  const remark=($('reRemark').value||'').trim();
  if(!primary){showToast('名称或关键词不能为空',true);$('rePrimary').focus();return;}
  const payload=reKind==='keywords'
    ?{op:'edit_item',id:reRowId,keyword:primary,group,remark,...kwQueryOpts()}
    :{op:'edit_item',id:reRowId,name:primary,url:($('reUrl').value||'').trim(),group,remark,...auQueryOpts()};
  try{
    const d=await api('/api/v1/workbench/'+reKind,'POST',payload);
    $('rowEditModal').close();
    if(reKind==='keywords'){applyKwPayload(d);await refreshKeywords();}
    else{applyAuPayload(d);await refreshAuthors();}
    showToast(d.message||'已保存修改');
  }catch(e){showToast(e.message,true);}
}
$('groupManagerModal')&&$('groupManagerModal').addEventListener('click',e=>{if(e.target===$('groupManagerModal'))$('groupManagerModal').close();});
$('rowEditModal')&&$('rowEditModal').addEventListener('click',e=>{if(e.target===$('rowEditModal'))$('rowEditModal').close();});
function auRunSingle(url){$('authorUrl').value=url;submitCollection('homepage');}
async function migrateLegacyArchive(){
  try{
    await kwSyncJianghu();await api('/api/v1/workbench/artworks','POST',{op:'sync_jianghu'});await Promise.all([refreshKeywords(),refreshArtworks()]);
    showToast('旧版历史词库与作品档案已同步合并');
  }catch(e){showToast('迁移失败：'+e.message,true);}
}

function copyAiText(text,msg){
  if(!text)return;
  navigator.clipboard&&navigator.clipboard.writeText(text);
  showToast(msg||'已复制到剪贴板');
}
function copyAiSnippet(elId){
  const el=$(elId);
  if(el)copyAiText((el.textContent||'').trim(),'已复制到剪贴板，可直接粘贴给 AI');
}

// Artworks library
let artworkReadSequence=0;
async function refreshArtworks(){
  const sequence=++artworkReadSequence;
  const sortBy=($('artSortBy')&&$('artSortBy').value)||'collected_at';
  const artType=($('artTypeFilter')&&$('artTypeFilter').value)||'all';
  const statusFilter=($('artStatusFilter')&&$('artStatusFilter').value)||'all';
  const params=new URLSearchParams({
    mode:activeArtView,search:$('artSearch').value||'',artwork_type:artType,
    sort_by:sortBy,sort_dir:sortBy==='seq'?'asc':'desc',
    include_kw:$('artIncludeKw').value||'',exclude_kw:$('artExcludeKw').value||'',
    min_likes:$('artMinLikes').value||'0',min_favorites:($('artMinFavorites')&&$('artMinFavorites').value)||'0',min_comments:$('artMinComments').value||'0',min_images:$('artMinImages').value||'0'
  });
  const d=await api('/api/v1/workbench/artworks?'+params.toString());
  if(sequence!==artworkReadSequence)return;
  const rawItems=d.items||[];
  const statusHit=r=>{
    const s=String(r.download_status||'');
    if(statusFilter==='problem')return /待补|失败|未知|验证|搁置/.test(s);
    if(statusFilter==='done')return /已下载|成功/.test(s);
    if(statusFilter==='pending')return s.includes('待补');
    if(statusFilter==='blocked')return s.includes('拦截');
    if(statusFilter==='unknown')return /未知|部分失败/.test(s);
    return true;
  };
  const statusItems=statusFilter==='all'?rawItems:rawItems.filter(statusHit);
  wbArtworks=artType==='AI任务'?statusItems:statusItems.filter(r=>!r.is_shell_job);
  $('artSummaryText').textContent=`当前 ${d.current_count||0} 条 · 历史 ${d.history_count||0} 条 · 显示 ${wbArtworks.length} 条`;
  const body=$('artTableBody');
  if(!wbArtworks.length){body.innerHTML='<tr><td colspan="13" style="text-align:center;color:var(--muted)">暂无符合条件的作品记录</td></tr>';return;}
  const fmtStat=v=>(v===null||v===undefined||v==='')?'—':String(v);
  body.innerHTML=wbArtworks.map(r=>{
    const openPath=r.ingested_dir||r.save_path||'';
    const stText=String(r.download_status||'已读取未下载');
    const stCls=(stText.includes('已下载')||stText==='成功')?'ok':((stText.includes('失败')||stText.includes('验证')||stText.includes('待补')||stText.includes('拦截')||stText.includes('未知')||stText.includes('搁置'))?'warn':'');
    const ingestBadge=r.ingest_status?` <span class="badge ${String(r.ingest_status).includes('已入库')?'ok':'warn'}">${esc(r.ingest_status)}</span>`:'';
    const pubDate=String(r.publish_time||'').trim()||'—';
    const colRaw=String(r.collected_at||'').trim();
    const colShort=colRaw?colRaw.slice(5,16):'—';
    const srcChan=r.source_channel||(r.artwork_type==='AI任务'?'AI':((r.extract_type==='剪贴板'||r.keyword==='剪贴板采集')?'剪贴板':(String(r.extract_type||'').includes('主页')?'主页':(r.extract_type==='单作品'?'单作品':'关键词'))));
    const srcDetail=r.source_detail||r.keyword||r.extract_type||'—';
    const hasMissingStat=[r.comments,r.favorites,r.likes].some(v=>v===null||v===undefined||v==='');
    const statTip=hasMissingStat?'title="列表页接口未返回该项计数，下载或补全详情后自动更新"':'';
    const canDownload=r.artwork_type!=='AI任务'||!!r.url;
    return `<tr>
      <td><input type="checkbox" ${r.checked?'checked':''} onchange="artToggle('${esc(r.id)}',this.checked)"></td>
      <td>${esc(r.seq)}</td>
      <td><span class="badge">${esc(r.artwork_type)}</span></td>
      <td><span class="badge">${esc(srcChan)}</span></td>
      <td class="cell-ellipsis" title="${esc(srcDetail)}">${esc(srcDetail)}</td><td>${esc(r.author)}</td>
      <td class="cell-ellipsis" title="${esc(openPath||r.title)}">${esc(r.title)}</td>
      <td style="white-space:nowrap;font-variant-numeric:tabular-nums" ${statTip}>${esc(fmtStat(r.comments))} / ${esc(fmtStat(r.favorites))} / ${esc(fmtStat(r.likes))}</td>
      <td style="white-space:nowrap">${esc(pubDate)}</td>
      <td style="white-space:nowrap;font-variant-numeric:tabular-nums" title="${esc(colRaw||'未记录')}">${esc(colShort)}</td>
      <td>${esc(r.image_count)}</td>
      <td><span class="badge ${stCls}">${esc(stText)}</span>${ingestBadge}</td>
      <td style="white-space:nowrap">${openPath?`<button class="mini-btn" type="button" data-open-dir="${esc(openPath)}">打开</button> `:''}${canDownload?`<button class="mini-btn" type="button" onclick="downloadOneArtwork('${esc(r.id)}','${esc(r.url)}',${openPath?1:0})">${openPath?'重下':'下载'}</button>`:'<span style="color:var(--muted)">—</span>'}${r.url&&String(r.url).startsWith('http')?` <a class="mini-btn" href="${esc(r.url)}" target="_blank" rel="noreferrer" style="text-decoration:none">原链</a>`:''}</td>
    </tr>`;
  }).join('');
}
async function artToggle(id,checked){await api('/api/v1/workbench/artworks','POST',{op:'toggle',id,checked});refreshArtworks();}
async function artBatch(mode){await api('/api/v1/workbench/artworks','POST',{op:'batch_select',mode});refreshArtworks();}
function artResetFilters(){
  ['artSearch','artIncludeKw','artExcludeKw'].forEach(id=>{if($(id))$(id).value='';});
  if($('artTypeFilter'))$('artTypeFilter').value='all';
  if($('artStatusFilter'))$('artStatusFilter').value='all';
  if($('artSortBy'))$('artSortBy').value='collected_at';
  ['artMinLikes','artMinFavorites','artMinComments','artMinImages'].forEach(id=>{if($(id))$(id).value='0';});
  refreshArtworks();
  showToast('已重置作品筛选条件');
}
async function artDeleteSelected(){await api('/api/v1/workbench/artworks','POST',{op:'delete'});refreshArtworks();}
async function artExportCsv(){
  const d=await api('/api/v1/workbench/artworks','POST',{op:'export_csv'});
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+(d.csv||'')],{type:'text/csv;charset=utf-8'}));a.download='artworks.csv';a.click();
}
async function downloadOneArtwork(id,url,forceRedownload){
  if(!id&&!url)return;
  showToast('正在读取作品并下载素材…');
  try{
    const res=await api('/api/v1/workbench/artworks','POST',{op:'download',ids:[String(id)],mode:activeArtView,force_redownload:!!forceRedownload,output_dir:getOutputDir()});
    refreshArtworks();refreshDashboard();
    if(res.downloaded_works>0){showToast(res.message||'下载完成');return;}
    if(res.fallback_urls&&res.fallback_urls.length){$('input').value=res.fallback_urls.join('\n');activateNavTab('tabSingle');$('go').click();return;}
    showToast(res.message||'未下载成功',true);
  }catch(e){showToast('下载失败：'+e.message,true);}
}
async function downloadCheckedArtworks(){
  const checkedIds=wbArtworks.filter(r=>r.checked).map(r=>String(r.id));
  if(!checkedIds.length){showToast('请先在作品列表中勾选要下载的作品',true);return;}
  const button=$('downloadCheckedBtn');
  if(button.disabled||activeJob){showToast('已有下载任务正在处理，请查看下载进度');return;}
  button.disabled=true;
  showToast(`正在处理已选 ${checkedIds.length} 条作品…`);
  try{
    const res=await api('/api/v1/workbench/artworks','POST',{op:'download',ids:checkedIds,mode:activeArtView,output_dir:getOutputDir()});
    refreshArtworks();refreshDashboard();
    showToast(res.message||'批量下载完成',res.downloaded_works===0&&!(res.fallback_urls&&res.fallback_urls.length));
    if(res.fallback_urls&&res.fallback_urls.length){
      $('input').value=res.fallback_urls.join('\n');activateNavTab('tabSingle');$('go').click();
    }
  }catch(e){showToast('下载失败：'+e.message,true);}
  finally{button.disabled=false;}
}
async function retryProblemArtworks(){
  const ids=wbArtworks.filter(r=>r.artwork_type!=='AI任务'&&r.url).map(r=>String(r.id));
  if(!ids.length){showToast('当前筛选下没有可重试的异常作品',true);return;}
  const button=$('retryProblemBtn');
  if(button.disabled||activeJob){showToast('已有下载任务正在处理，请查看下载进度');return;}
  button.disabled=true;
  showToast(`正在重试 ${ids.length} 条异常作品…`);
  try{
    const res=await api('/api/v1/workbench/artworks','POST',{op:'download',ids,mode:activeArtView,output_dir:getOutputDir()});
    refreshArtworks();refreshDashboard();
    showToast(res.message||'批量重试完成',res.downloaded_works===0&&!(res.fallback_urls&&res.fallback_urls.length));
    if(res.fallback_urls&&res.fallback_urls.length){
      $('input').value=res.fallback_urls.join('\n');activateNavTab('tabSingle');$('go').click();
    }
  }catch(e){showToast('重试失败：'+e.message,true);}
  finally{button.disabled=false;}
}
async function ingestCheckedArtworks(){
  const checkedIds=wbArtworks.filter(r=>r.checked).map(r=>String(r.id));
  if(!checkedIds.length){showToast('请先勾选已下载的作品',true);return;}
  showToast(`正在按本地规则分类入库已选 ${checkedIds.length} 条作品…`);
  try{
    const res=await api('/api/v1/workbench/artworks','POST',{op:'ingest',ids:checkedIds,mode:activeArtView});
    refreshArtworks();refreshDashboard();
    showToast(res.message||'入库完成');
  }catch(e){showToast('入库失败：'+e.message,true);}
}

// Engine / Login
async function engineAction(action,params){
  const silent=!!(params&&params.silent);
  const box=$('loginActionFeedback');
  const pendingMsg='正在向底层引擎发送指令…';
  if(!silent){
    if(box){box.hidden=false;box.textContent=pendingMsg;}
    showToast(pendingMsg);
  }
  try{
    const res=await api('/api/v1/workbench/engine','POST',{action,params});
    const okMsg=res.message||(res.status==='ok'?'底层指令执行完成':JSON.stringify(res));
    if(box)box.textContent=okMsg;
    if(!silent||(res.windows_focused&&res.windows_focused>0))showToast(okMsg);
    setTimeout(()=>{refreshCollectionCapabilities();refreshArtworks();},900);
    return res;
  }catch(e){
    const errMsg='操作提示：'+e.message;
    if(box){box.hidden=false;box.textContent=errMsg;}
    if(!silent)showToast(errMsg,true);
    return null;
  }
}
async function switchBrowserProfile(){
  const name=($('profileSelect')&&$('profileSelect').value)||'default';
  const r=await engineAction('switch_profile',{name});
  if(r&&r.status==='ok')await refreshCollectionCapabilities();
}
async function createBrowserProfile(){
  const r=await openInputModal({sub:'多账号浏览器档案 DIY',title:'新建独立浏览器档案',valueLabel:'档案名称（如：小红书备用号 / 抖音二号）',value:'',placeholder:'例如：小红书备用号'});
  const name=(r&&r.value||'').trim();
  if(!name)return;
  const res=await engineAction('create_profile',{name});
  if(res&&res.status==='ok'){
    await refreshCollectionCapabilities();
    if($('profileSelect'))$('profileSelect').value=name;
    await switchBrowserProfile();
  }
}
async function deleteBrowserProfile(){
  const name=($('profileSelect')&&$('profileSelect').value)||'default';
  if(name==='default'){showToast('默认主账号档案不可删除',true);return;}
  const res=await engineAction('delete_profile',{name});
  if(res&&res.status==='ok')await refreshCollectionCapabilities();
}
async function openLocalDir(pathStr){
  try{await api('/api/v1/workbench/engine','POST',{action:'open_folder',params:{path:pathStr||getOutputDir()}});}
  catch(e){showToast('打开目录失败：'+e.message,true);}
}
function openDownloadDir(){openLocalDir(getOutputDir());}
document.addEventListener('click',e=>{
  const btn=e.target&&e.target.closest?e.target.closest('[data-open-dir]'):null;
  if(btn&&btn.dataset.openDir)openLocalDir(btn.dataset.openDir);
});
function stopKeywordCollection(){kwBatchQueueStop=true;activeKeywordRun=false;$('kwVisualBar')&&$('kwVisualBar').classList.remove('active');engineAction('stop_keyword',{});}
$('btnBannerStartDouyin').addEventListener('click',()=>engineAction('start_engine',{platform:'douyin'}));
$('btnBannerPopBrowser').addEventListener('click',()=>engineAction('bring_verify_browser',{platform:activeEnginePlatform}));
$('btnBannerResume').addEventListener('click',()=>engineAction('resume_keyword',{}));
$('btnBannerVerify').addEventListener('click',()=>activateNavTab('tabLogin'));
$('engineStatusPill').addEventListener('click',()=>activateNavTab('tabLogin'));

// Original single download & collection wiring
const settings=()=>({
  output_dir:getOutputDir(),
  mode:($('d_delay_mode')&&$('d_delay_mode').value)||localStorage.getItem(MODE_KEY)||'auto',
  image_format:($('d_image_format')&&$('d_image_format').value)||localStorage.getItem(FORMAT_KEY)||'jpg',
  title_template:($('d_title_template')&&$('d_title_template').value.trim())||'评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}',
  set_file_time_to_publish:$('d_set_file_time_to_publish')?$('d_set_file_time_to_publish').checked:true,
  auto_ingest_material:$('k_auto_ingest_chip')?$('k_auto_ingest_chip').checked:($('d_auto_ingest_material')?$('d_auto_ingest_material').checked:true),
  skip_downloaded_history:$('k_skip_dup_chip')?$('k_skip_dup_chip').checked:($('d_skip_downloaded_history')?$('d_skip_downloaded_history').checked:true)
});
function setCollectionStatus(kind,task,err){
  const box=$(kind+'Status');if(!box)return;
  if(err){box.hidden=false;box.dataset.state='error';box.innerHTML=`<strong>无法开始：</strong>${esc(err)}`;return;}
  if(!task){box.hidden=true;return;}
  box.hidden=false;box.dataset.state=task.status||'queued';
  box.innerHTML=`<strong>${esc(task.label||'发现任务')}：</strong>${esc(task.message||'正在处理')}`;
}
function updateKwKpis(kp,runningHint=false){
  if(!kp||typeof kp!=='object')return;
  const targetVal=kp.target!=null?kp.target:(Number($('keywordCount').value)||'全部');
  const crawled=kp.crawled||0,qualified=kp.qualified||0,downloaded=kp.downloaded||0;
  if($('kwKpiTarget'))$('kwKpiTarget').textContent=String(targetVal===0?'全部':targetVal);
  if($('kwKpiCrawled'))$('kwKpiCrawled').textContent=String(crawled);
  if($('kwKpiQualified'))$('kwKpiQualified').textContent=String(qualified);
  if($('kwKpiDownloaded'))$('kwKpiDownloaded').textContent=String(downloaded);
  const bar=$('kwVisualBar');if(!bar)return;
  const activePhases=['starting','scanning','scanned','qualified','list_ready','downloading','crawling'];
  const isActive=runningHint||activeKeywordRun||activePhases.includes(kp.phase);
  bar.classList.toggle('active',isActive);
  let pct=0;
  if(kp.phase==='completed'){pct=100;}
  else if(kp.phase==='downloading'){
    const den=Math.max(1,Number(kp.qualified)||Number(targetVal)||1);
    pct=Math.max(35,Math.round((downloaded/den)*100));
  }else if(isActive){
    const den=Math.max(1,Number(targetVal)||20);
    pct=qualified>0?Math.min(75,Math.max(18,Math.round((qualified/den)*70))):(crawled>0?18:10);
  }
  bar.style.width=Math.min(100,pct)+'%';
  if($('kwProgressSummary'))$('kwProgressSummary').textContent=kp.message||(isActive?'正在实时读取搜索页…':'等待开始采集');
}
async function pollCollection(kind,jobId){
  try{
    const t=await api('/api/v1/collections/jobs/'+encodeURIComponent(jobId));
    setCollectionStatus(kind,t,null);refreshDashboard();
    if(kind==='keyword'){
      if(t.keyword_progress)updateKwKpis(t.keyword_progress,true);
      refreshArtworks();
    }
    if(['completed','completed_zero','partial','cancelled','error','unknown','accepted','verification_required','login_required'].includes(t.status)){
      if(kind==='keyword'){
        activeKeywordRun=false;
        const bar=$('kwVisualBar');
        if(bar){bar.classList.remove('active');if(t.status==='completed')bar.style.width='100%';}
        refreshKeywords();refreshArtworks();refreshDashboard();
        showToast(t.message||'关键词采集已结束',t.status!=='completed'&&t.status!=='accepted');
      }else{
        refreshArtworks().catch(e=>showToast('作品列表刷新失败：'+e.message,true));
      }
      return t;
    }
    await new Promise(resolve=>setTimeout(resolve,1000));
    return await pollCollection(kind,jobId);
  }catch(e){
    await new Promise(resolve=>setTimeout(resolve,1500));
    return await pollCollection(kind,jobId);
  }
}
async function runSingleKeywordJob(keyword){
  const rawCount=$('keywordCount').value;
  const numCount=rawCount===''?20:Number(rawCount);
  const allResults=numCount===0;
  const mediaType=($('k_media_type')&&$('k_media_type').value)||'image';
  const isJg=activeKwPlatform==='juguang';
  const req={
    platform:activeKwPlatform,
    keyword,
    count:allResults?0:Math.max(1,Math.min(500,numCount)),
    all_results:allResults,
    min_images:Number($('minImages').value)||0,
    max_images:Number($('maxImages').value)||20,
    media_type:mediaType,
    allow_video:mediaType!=='image',
    no_filter:false,
    direct_download:!!($('k_direct_download')&&$('k_direct_download').checked),
    juguang_category:($('k_juguang_category')&&$('k_juguang_category').value)||'客资收集',
    web_sort:isJg?(($('k_juguang_sort')&&$('k_juguang_sort').value)||'阅读量'):(($('k_web_sort')&&$('k_web_sort').value)||'综合排序'),
    web_publish_time:isJg?(($('k_juguang_time')&&$('k_juguang_time').value)||'近7日'):(($('k_web_publish_time')&&$('k_web_publish_time').value)||'不限'),
    ...settings()
  };
  activeKeywordRun=true;
  updateKwKpis({target:allResults?'全部':req.count,crawled:0,qualified:0,downloaded:0,phase:'starting',message:`正在打开 ${platLabel(activeKwPlatform)} 搜索：【${keyword}】`},true);
  setCollectionStatus('keyword',{status:'discovering',label:`采集：${keyword}`,message:'正在连接采集内核并检索搜索列表…'},null);
  const task=await api('/api/v1/collections/keyword','POST',req);
  return await pollCollection('keyword',task.job_id);
}
async function ensureEngineOnline(platform){
  const cap=await api('/api/v1/collections/capabilities').catch(()=>null);
  if(cap&&cap.status==='online'&&(cap.engine_mode==='native-playwright'||cap.active_platform===platform))return true;
  if(cap&&cap.status!=='online'){
    const platName=platLabel(platform);
    showToast(`正在唤醒内置${platName}浏览器引擎…`);
    await api('/api/v1/workbench/engine','POST',{action:'start_engine',params:{platform}}).catch(()=>{});
    for(let i=0;i<30;i++){
      await new Promise(r=>setTimeout(r,1000));
      const next=await api('/api/v1/collections/capabilities').catch(()=>null);
      if(next&&next.status==='online'){
        await refreshCollectionCapabilities();
        return true;
      }
    }
    throw new Error('采集引擎未能就绪，请前往「平台登录」检查');
  }
  return true;
}
async function submitCollection(kind){
  const btn=$(kind==='homepage'?'startHomepage':'startKeyword');
  if(kind==='homepage'){
    const profile_url=($('authorUrl').value||'').trim()||(wbAuthors.find(a=>a.checked)||{}).url||'';
    if(!profile_url){setCollectionStatus(kind,null,'请填写或勾选一个作者主页链接');showToast('请先填写或勾选主页链接',true);return;}
    const hpPlat=/xiaohongshu\.com|xhslink\.(com|cn)/i.test(profile_url)?'xiaohongshu':'douyin';
    btn.disabled=true;
    setCollectionStatus(kind,{status:'queued',label:'准备引擎',message:'正在检查引擎状态并连接采集流程…'},null);
    try{
      await ensureEngineOnline(hpPlat);
      const req={
        platform:hpPlat,
        profile_url,
        max_works:Math.max(1,Math.min(hpPlat==='xiaohongshu'&&!$('a_direct_download').checked?150:50,Number($('a_max_per_author').value)||10)),
        min_images:Number($('a_min_images').value||0),
        max_images:Number($('a_max_images').value||50),
        direct_download:$('a_direct_download').checked,
        ...settings()
      };
      showToast(`已启动${hpPlat==='xiaohongshu'?'小红书':'抖音'}作者主页采集`);
      const task=await api('/api/v1/collections/homepage','POST',req);
      await pollCollection('homepage',task.job_id);
    }catch(e){setCollectionStatus(kind,null,e.message);showToast(e.message,true);}
    finally{
      btn.disabled=false;
      $('a_direct_download').checked=false;
      btn.textContent='采集主页';
    }
    return;
  }
  const typed=($('keywordValue').value||'').trim();
  const targets=typed?[typed]:wbKeywords.filter(k=>k.checked).map(k=>k.keyword);
  if(!targets.length){setCollectionStatus('keyword',null,'请填写关键词或在上方表格勾选至少一个关键词');showToast('请先输入或勾选至少一个关键词',true);return;}
  $('kwLaunchCard')&&$('kwLaunchCard').scrollIntoView({behavior:'smooth',block:'nearest'});
  kwBatchQueueStop=false;btn.disabled=true;
  try{
    await ensureEngineOnline(activeKwPlatform);
    for(let idx=0;idx<targets.length;idx++){
      if(kwBatchQueueStop)break;
      const kw=targets[idx];
      const prefix=targets.length>1?`批量队列 ${idx+1}/${targets.length} · `:'';
      showToast(`${prefix}已启动采集：【${kw}】`);
      const finalTask=await runSingleKeywordJob(kw);
      if(finalTask&&['verification_required','login_required','cancelled'].includes(finalTask.status))break;
    }
  }catch(e){
    activeKeywordRun=false;$('kwVisualBar')&&$('kwVisualBar').classList.remove('active');
    setCollectionStatus('keyword',null,e.message);showToast('采集未能启动：'+e.message,true);
  }finally{
    activeKeywordRun=false;btn.disabled=false;updateStartKeywordLabel();
  }
}
$('a_direct_download').addEventListener('change',()=>{
  $('startHomepage').textContent=$('a_direct_download').checked?'采集主页并下载素材':'采集主页';
});
$('artRefreshBtn').addEventListener('click',async()=>{
  const button=$('artRefreshBtn');
  button.disabled=true;
  try{await refreshArtworks();}
  catch(e){showToast('作品列表刷新失败：'+e.message,true);}
  finally{button.disabled=false;}
});
$('startHomepage').addEventListener('click',()=>submitCollection('homepage'));
$('startKeyword').addEventListener('click',()=>submitCollection('keyword'));

$('go').addEventListener('click',async()=>{
  const text=$('input').value.trim();if(!text){$('input').focus();return;}
  $('go').disabled=true;$('go').textContent='正在提交…';
  $('results').innerHTML='';$('results').classList.remove('show');
  $('progressBar').classList.add('active');$('stateDot').className='state-dot running';
  $('progressBar').style.width='0%';
  $('progressText').textContent='已处理 0 / 0';
  $('successText').textContent='成功 0 · 跳过 0 · 失败 0';
  $('statusSub').textContent='正在提交下载任务…';
  try{
    const d=await api('/api/jobs','POST',{text,...settings()});
    trackDownloadJob(d.job_id);
  }catch(e){
    $('go').disabled=false;$('go').textContent='立即解析并下载';
    $('progressBar').classList.remove('active');$('stateDot').className='state-dot error';$('statusSub').textContent=e.message;
  }
});

function trackDownloadJob(id){
  activeJob=id;
  $('downloadRecovery').hidden=true;
  try{sessionStorage.setItem(DOWNLOAD_JOB_KEY,id);}catch(_){}
  if(pollTimer)clearTimeout(pollTimer);
  $('go').disabled=true;
  pollJob(id);
}
function stopTrackingDownload(clearSaved=false){
  activeJob=null;
  $('go').disabled=false;
  $('go').textContent='立即解析并下载';
  $('progressBar').classList.remove('active');
  if(clearSaved){try{sessionStorage.removeItem(DOWNLOAD_JOB_KEY);}catch(_){}}
}
function downloadItemDescription(item){
  const engineNames={
    'local-cli':'小红书本地 CLI',
    'douyin-fast-api':'抖音原画秒解',
    'douyin-edge':'抖音 Edge 兜底',
    'yt-dlp':'yt-dlp 通用引擎',
    'history':'本地历史复用',
    'cn-kuaishou':'快手直解',
    'cn-weibo':'微博直解',
    'cn-toutiao':'今日头条',
    'cn-doubao':'豆包 AI',
    'cn-jimeng':'即梦 AI',
    'cn-pipixia':'皮皮虾',
    'cn-pipigx':'皮皮搞笑',
    'cn-zuiyou':'最右'
  };
  if(item.deduplicated)return '本地已存在';
  const stages={note_detail:'读取详情',media_write:'保存素材'};
  const message=item.error||item.save_dir||(item.success?'素材已保存':'未下载成功');
  const http=item.http_status?'HTTP '+item.http_status:'';
  return [engineNames[item.engine],stages[item.failure_stage],http,message].filter(Boolean).join(' · ');
}
async function pollJob(id){
  try{
    const j=await api('/api/jobs/'+encodeURIComponent(id));
    if(activeJob!==id)return;
    const total=j.total||0,done=j.done||0,success=j.success||0,failed=j.failed||0,skipped=j.skipped||0;
    $('progressBar').style.width=(total?Math.min(100,Math.round(done/total*100)):0)+'%';
    $('progressText').textContent=`已处理 ${done} / ${total}`;
    $('successText').textContent=`成功 ${success} · 跳过 ${skipped} · 失败 ${failed}`;
    const resEl=$('results');
    if(j.items&&j.items.length){
      resEl.classList.add('show');
      resEl.innerHTML=j.items.slice(-8).map((it,index)=>{
        const title=it.title||it.note_id||`第 ${Math.max(0,done-Math.min(j.items.length,8))+index+1} 条作品`;
        const description=downloadItemDescription(it);
        const state=it.success||it.deduplicated?'ok':'fail';
        return `<div class="result ${state}" style="display:flex;justify-content:space-between;align-items:center;gap:8px"><div style="min-width:0;flex:1"><strong>${esc(title)}</strong><div title="${esc(description)}" style="color:var(--muted);font-size:11px;margin-top:2px;overflow-wrap:anywhere">${esc(description)}</div></div>${it.save_dir?`<button class="mini-btn" type="button" data-open-dir="${esc(it.save_dir)}">打开</button>`:''}</div>`;
      }).join('');
    }
    if(['completed','error','paused'].includes(j.status)){
      stopTrackingDownload();
      $('stateDot').className='state-dot '+(j.status!=='completed'||failed?'error':'done');
      $('statusSub').textContent=j.status==='paused'?
        (j.pause_reason==='rate_limit'?'平台限制请求频率，已暂停下载':'平台要求登录或验证，已暂停下载'):
        (j.status==='error'?(j.error||'任务执行失败'):
          (failed?(success||skipped?'任务结束，部分作品下载失败':'任务结束，全部下载失败'):
            (j.workbench_sync_error||'任务处理完毕')));
      showDownloadRecovery(id,j);
      refreshDashboard();refreshArtworks();
      return;
    }
    const queued=j.status==='queued'||j.status==='waiting';
    $('go').textContent=queued?'等待执行…':'下载处理中…';
    $('stateDot').className='state-dot running';
    $('progressBar').classList.toggle('active',!queued);
    $('statusSub').textContent=queued?'已进入下载队列，等待前序任务结束':
      (failed>0&&success===0&&skipped===0?'正在处理，暂未下载成功。请查看下方失败原因。':'正在按队列解析并下载作品');
    pollTimer=setTimeout(()=>pollJob(id),700);
  }catch(e){
    if(activeJob!==id)return;
    if(e.status===404){
      stopTrackingDownload(true);
      $('statusSub').textContent='该任务已不在运行，查看历史档案核对结果';
      return;
    }
    $('statusSub').textContent='暂时无法读取任务进度，正在重新连接…';
    pollTimer=setTimeout(()=>pollJob(id),1500);
  }
}

function showDownloadRecovery(id,job){
  const failed=$('retryFailedDownload'), remaining=$('resumeRemainingDownload');
  failed.hidden=!(job.items||[]).some(item=>item.work_ref&&!item.success&&!item.deduplicated);
  remaining.hidden=!(job.pending_refs||[]).some(Boolean);
  failed.dataset.jobId=remaining.dataset.jobId=id;
  $('downloadRecovery').hidden=failed.hidden&&remaining.hidden;
}
async function recoverDownload(event,scope){
  const button=event.currentTarget;
  const id=button.dataset.jobId;
  if(!id||activeJob)return;
  const buttons=[$('retryFailedDownload'),$('resumeRemainingDownload')];
  buttons.forEach(el=>el.disabled=true);
  try{
    const result=await api('/api/jobs','POST',{retry_job_id:id,retry_scope:scope},
      {'Idempotency-Key':`workbench-recovery-${id}-${scope}`});
    trackDownloadJob(result.job_id);
  }catch(e){showToast(e.message,true);}
  finally{buttons.forEach(el=>el.disabled=false);}
}
$('retryFailedDownload').addEventListener('click',event=>recoverDownload(event,'failed'));
$('resumeRemainingDownload').addEventListener('click',event=>recoverDownload(event,'remaining'));
$('queueList').addEventListener('click',event=>{
  const button=event.target.closest('[data-download-job]');
  if(button){activateNavTab('tabSingle');trackDownloadJob(button.dataset.downloadJob);}
});

async function refreshCollectionCapabilities(){
  try{
    const d=await api('/api/v1/collections/capabilities');
    const pill=$('engineStatusPill'),txt=$('engineStatusText'),banner=$('globalEngineAlert');
    const online=d.status==='online';
    activeEnginePlatform=d.active_platform||'douyin';
    pill.dataset.online=online?'true':'false';
    pill.dataset.verify=d.verification_required?'true':'false';
    if($('btnBannerStartDouyin'))$('btnBannerStartDouyin').hidden=online;
    if($('btnBannerPopBrowser'))$('btnBannerPopBrowser').hidden=!d.verification_required;
    if($('btnBannerResume'))$('btnBannerResume').hidden=!d.verification_required;
    if(!online){
      lastVerifyKey='';
      txt.textContent='底层引擎离线';banner.classList.add('show');
      $('alertTitle').textContent='江湖原生会话引擎离线';
      $('alertBody').textContent='公开链接可直接在本页高速下载；若需抖音/小红书搜索列表与主页发现，可点右侧“启动抖音引擎”静默拉起。';
    }else if(d.verification_required){
      txt.textContent='等待人机验证';banner.classList.add('show');
      $('alertTitle').textContent='平台触发人机验证（需要人工辅助）';
      $('alertBody').textContent='已自动尝试弹出并置顶验证浏览器；请完成滑块/扫码后点击右侧“已完成验证，继续采集”。';
      const vKey=(d.keyword_progress&&(d.keyword_progress.job_id||d.keyword_progress.keyword))||'verify';
      if(vKey!==lastVerifyKey){
        lastVerifyKey=vKey;
        showToast('触发人机验证：正在弹出并置顶验证浏览器窗口，请人工完成验证',true);
        engineAction('bring_verify_browser',{platform:activeEnginePlatform,silent:true});
      }
    }else{
      lastVerifyKey='';
      txt.textContent=d.engine_mode==='native-playwright'?'内置双核引擎就绪':((activeEnginePlatform==='xiaohongshu'?'小红书':'抖音')+'引擎在线');banner.classList.remove('show');
    }
    const chLabel=d.browser_channel==='chrome'?'Chrome':(d.browser_channel==='chromium'?'Chromium':'Edge');
    const drvLabel=d.browser_driver==='patchright'?'Patchright 反检测内核':'Playwright 内核';
    const sel=$('profileSelect');
    if(sel&&Array.isArray(d.profiles)&&d.profiles.length){
      sel.innerHTML=d.profiles.map(p=>`<option value="${esc(p.name)}" ${p.active?'selected':''}>${esc(p.label||p.name)}</option>`).join('');
      if(d.active_profile)sel.value=d.active_profile;
    }
    const rhBox=$('engineRuleHealthBox');
    if(rhBox){
      const rh=d.rule_health||{};
      const fmtRh=(label,st)=>{
        if(!st)return `${label}：等待自检`;
        const map={ok:'接口监听正常',dom_fallback:'页面兜底生效',possible_rule_break:'⚠️ 疑似网页改版/需检查登录',gate_blocked:'⚠️ 触发人机验证'};
        const zh=map[st.status]||'等待采集自检';
        return `${label}：<strong>${esc(zh)}</strong>（接口 ${st.api_items||0} / 页面 ${st.dom_items||0}）`;
      };
      rhBox.innerHTML=`<div>驱动内核：<span class="badge ok">${esc(drvLabel)}</span> · 浏览器：<strong>${esc(chLabel)}</strong> · 当前档案：<strong>${esc(d.active_profile==='default'?'默认主账号':(d.active_profile||'默认主账号'))}</strong></div><div style="margin-top:4px">${fmtRh('抖音规则',rh.douyin)} &nbsp;|&nbsp; ${fmtRh('小红书规则',rh.xiaohongshu)} &nbsp;|&nbsp; ${fmtRh('聚光规则',rh.juguang)}</div>`;
    }
    const kwMsg=online?(d.verification_required?'内置浏览器等待人机验证。':(d.engine_mode==='native-playwright'?`内置 ${chLabel}（${drvLabel}）在线（接口直听 + 抖音/小红书/聚光随时开采），采集后自动下载入库。`:`底层引擎在线（${platLabel(activeEnginePlatform)}），采集作品将自动送入统一下载队列。`)):'底层引擎离线（公开单链接仍可直接使用）。';
    $('keywordCapability').textContent=kwMsg;$('homepageCapability').textContent=kwMsg;
    const kp=d.keyword_progress;
    const isStaleVerifyKp=kp&&(kp.phase==='verification'||kp.status==='verification_required')&&!d.verification_required;
    if(kp&&typeof kp==='object'&&!isStaleVerifyKp){
      updateKwKpis(kp,d.busy===true);
      const counter=`${kp.qualified||0}:${kp.downloaded||0}:${kp.crawled||0}`;
      if(lastKwCounter&&counter!==lastKwCounter)refreshArtworks();
      lastKwCounter=counter;
    }else if(!activeKeywordRun&&$('kwKpiTarget')){
      const c=Number($('keywordCount').value);
      $('kwKpiTarget').textContent=c===0?'全部':String(c||20);
    }
  }catch(_){}
}

const SOURCE_ZH={'downloader-history':'历史',clipboard:'剪贴板',web:'工作台',keyword:'关键词',homepage:'主页',api:'接口',ai:'AI'};
const STATUS_ZH={completed:'已完成',running:'进行中',queued:'排队中',pending:'等待中',paused:'已暂停',error:'失败',accepted:'已受理'};
function readableTaskTitle(r){
  const isHexId=v=>/^[0-9a-f]{24,}$/i.test(String(v||'').trim());
  const rawTitle=String((r&&r.title)||'').trim();
  if(rawTitle&&!isHexId(rawTitle))return rawTitle;
  const items=Array.isArray(r&&r.items)?r.items:[];
  const firstItemTitle=items.map(it=>String((it&&it.title)||'').trim()).find(t=>t&&!isHexId(t));
  const total=Number((r&&r.total)||items.length||0);
  if(firstItemTitle)return total>1?`${firstItemTitle} 等 ${total} 条`:firstItemTitle;
  if(total>1)return `批量下载任务（共 ${total} 条）`;
  if(total===1)return '单作品下载任务';
  if(r&&r.note_id&&!isHexId(r.note_id))return String(r.note_id);
  return '后台采集任务';
}
function renderTaskList(el,rows,emptyText){
  if(!rows||!rows.length){el.innerHTML=`<div class="panel-sub">${esc(emptyText)}</div>`;return;}
  el.innerHTML=rows.slice(0,30).map(r=>{
    const src=SOURCE_ZH[r.source]||r.source||'';
    const st=STATUS_ZH[r.status]||r.status||'';
    const processed=r.total?`已处理 ${r.done||0}/${r.total} · 成功 ${r.success||0} · 失败 ${r.failed||0}`:'';
    const tag=[src,st,processed].filter(Boolean).join(' · ');
    const titleText=readableTaskTitle(r);
    const metaText=r.completed_at||r.error||r.pause_reason||r.url||r.save_dir||processed||st||'';
    const openBtn=r.save_dir?`<button class="mini-btn" type="button" data-open-dir="${esc(r.save_dir)}">打开</button>`:'';
    const jobBtn=/^[0-9a-f]{32}$/.test(r.job_id||'')?`<button class="mini-btn" type="button" data-download-job="${esc(r.job_id)}">查看进度</button>`:'';
    return `<div class="task-row"><div class="task-main"><span class="task-title">${esc(titleText)}</span><span class="task-meta">${esc(metaText)}</span></div><div style="display:flex;align-items:center;gap:6px">${openBtn}${jobBtn}<span class="badge ${r.status==='completed'?'ok':(r.status==='error'?'bad':'')}">${esc(tag)}</span></div></div>`;
  }).join('');
}

async function refreshDashboard(){
  try{
    const d=await api('/api/v1/jobs?limit=40&history_offset=0');
    const c=d.collector||{};
    collectorEnabled=!!c.enabled;collectorOnline=!!c.online;
    const tog=$('collectorToggle');
    tog.setAttribute('aria-checked',collectorEnabled?'true':'false');
    $('collectorToggleText').textContent=collectorOnline?(collectorEnabled?'剪贴板采集 开':'剪贴板采集 关'):(collectorEnabled?'启动剪贴板开':'剪贴板 离线');
    const liveTasks=[...(d.running||[]),...(d.waiting||d.queue||[])];
    const recovery=(d.web_history||[]).filter(job=>job.status==='paused'||job.failed>0).slice(0,3);
    if($('waitingCount'))$('waitingCount').textContent=liveTasks.length;
    if($('queueList'))renderTaskList($('queueList'),[...liveTasks,...recovery],'暂无运行、排队或待处理的下载任务');
  }catch(_){}
}

$('collectorToggle').addEventListener('click',async()=>{
  try{await api('/api/v1/collector','POST',{enabled:!collectorEnabled});refreshDashboard();}catch(e){showToast(e.message,true);}
});

(async function initWorkbench(){
  const qs=new URLSearchParams(window.location.search||'');
  const qTheme=qs.get('theme'),qTab=qs.get('tab');
  const tabMap={single:'tabSingle',keyword:'tabKeyword',homepage:'tabHomepage',artworks:'tabArtworks',tasks:'tabArtworks',login:'tabLogin',settings:'tabSettings'};
  if(qTheme&&THEME_MODES.includes(qTheme))applyTheme(qTheme,false);
  try{const s=await api('/api/v1/workbench/settings');bindSettingFields(s);}catch(_){}
  if(qTheme&&THEME_MODES.includes(qTheme))applyTheme(qTheme,false);
  if(qTab&&tabMap[qTab]){activateNavTab(tabMap[qTab]);}
  else{
    let savedTab='';
    try{savedTab=localStorage.getItem('xhs-dl-active-tab')||'';}catch(_){}
    activateNavTab(savedTab&&$(savedTab)?savedTab:'tabKeyword');
  }
  $('keywordValue')&&$('keywordValue').addEventListener('input',updateStartKeywordLabel);
  function triggerAutoSave(){if(autoSaveTimer)clearTimeout(autoSaveTimer);autoSaveTimer=setTimeout(()=>saveAllWorkbenchSettings(false),400);}
  ['keywordCount','minImages','maxImages','k_media_type','k_web_sort','k_web_publish_time','k_juguang_category','k_juguang_time','k_juguang_sort','k_direct_download','a_max_per_author','a_min_images','a_max_images'].forEach(id=>{
    const el=$(id);
    if(el)el.addEventListener('change',()=>{
      if(id==='keywordCount'&&!activeKeywordRun&&$('kwKpiTarget')){$('kwKpiTarget').textContent=Number(el.value)===0?'全部':String(Number(el.value)||20);}
      if(id==='k_media_type')syncMediaTypeUi();
      triggerAutoSave();
    });
  });
  $('k_auto_ingest_chip')&&$('k_auto_ingest_chip').addEventListener('change',()=>{
    if($('d_auto_ingest_material'))$('d_auto_ingest_material').checked=$('k_auto_ingest_chip').checked;
    triggerAutoSave();
  });
  $('d_auto_ingest_material')&&$('d_auto_ingest_material').addEventListener('change',()=>{
    if($('k_auto_ingest_chip'))$('k_auto_ingest_chip').checked=$('d_auto_ingest_material').checked;
  });
  $('k_skip_dup_chip')&&$('k_skip_dup_chip').addEventListener('change',()=>{
    if($('d_skip_downloaded_history'))$('d_skip_downloaded_history').checked=$('k_skip_dup_chip').checked;
    triggerAutoSave();
  });
  $('d_skip_downloaded_history')&&$('d_skip_downloaded_history').addEventListener('change',()=>{
    if($('k_skip_dup_chip'))$('k_skip_dup_chip').checked=$('d_skip_downloaded_history').checked;
  });
  document.querySelectorAll('#settingsPanel input,#settingsPanel select').forEach(el=>el.addEventListener('change',triggerAutoSave));
  ['sw_theme_day_start','sw_theme_night_start','sw_theme_auto_style'].forEach(id=>{
    const el=$(id);
    if(el)el.addEventListener('change',()=>{
      if(!wbSettings.software)wbSettings.software={};
      wbSettings.software[id.replace('sw_','')]=el.type==='number'?Number(el.value||0):el.value;
      if(currentThemeMode==='auto')applyTheme('auto',false);
    });
  });
  const bindEnter=(id,fn)=>{const el=$(id);if(el)el.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();fn();}});};
  bindEnter('keywordValue',()=>submitCollection('keyword'));
  bindEnter('kwBatchInput',()=>kwAddFromInput());
  bindEnter('authorUrl',()=>submitCollection('homepage'));
  bindEnter('auBatchInput',()=>auAddFromInput());
  ['artIncludeKw','artExcludeKw','artMinLikes','artMinFavorites','artMinComments','artMinImages'].forEach(id=>bindEnter(id,()=>refreshArtworks()));
  try{
    const id=sessionStorage.getItem(DOWNLOAD_JOB_KEY);
    if(/^[0-9a-f]{32}$/.test(id||''))trackDownloadJob(id);
  }catch(_){}
  await Promise.allSettled([refreshKeywords(),refreshAuthors(),refreshArtworks(),refreshDashboard(),refreshCollectionCapabilities()]);
  setInterval(refreshDashboard,2500);
  setInterval(refreshCollectionCapabilities,2500);
})();
</script>
</body>
</html>
"""
