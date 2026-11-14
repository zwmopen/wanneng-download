"""xhs-dl V2 浏览器可视化界面。"""

import copy
import hashlib
import json
import threading
import time
import uuid
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

from xhs_dl.core.downloader import DELAY_MODES, extract_urls_from_text
from xhs_dl import __version__
from xhs_dl.branding import APP_NAME
from xhs_dl.core.unified_downloader import UnifiedDownloader
from xhs_dl.storage import history_path


JOBS = {}
JOBS_LOCK = threading.Lock()
JOB_CONDITION = threading.Condition(JOBS_LOCK)
JOB_IDEMPOTENCY = {}
DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads")
WEB_HISTORY_FILE = Path.home() / ".xhs-dl" / "web_history.json"
WEB_HISTORY_LOCK = threading.Lock()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIPBOARD_QUEUE_FILE = PROJECT_ROOT / "clipboard_pending_queue.json"
CLIPBOARD_HISTORY_FILE = PROJECT_ROOT / "clipboard_history.json"
COLLECTOR_HEARTBEAT_FILE = PROJECT_ROOT / "collector_heartbeat.json"
MAX_URLS_PER_JOB = 100
MAX_DASHBOARD_ROWS = 100


def _load_web_history():
    try:
        value = json.loads(WEB_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)][-100:]


WEB_HISTORY = _load_web_history()


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light">
<title>xhs-dl · 无水印下载</title>
<style>
:root{--radius-xl:28px;--radius-lg:22px;--radius-md:14px;--ease:220ms ease}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;font-family:"Microsoft YaHei UI","PingFang SC","Noto Sans CJK SC",sans-serif}
body[data-theme="neo"]{
  --bg:#e8edf3;--panel:#e2eaf2;--soft:#dce4ec;--line:#d1dbe4;
  --text:#242a31;--muted:#61758a;--primary:#263442;--primary-hover:#17222e;
  --active:#d7e4ef;--input:rgba(255,255,255,.34);--ok:#2f7b62;--bad:#a95055;
  --shadow:8px 8px 20px #c8d0d8,-8px -8px 20px #fbfdff;
  --shadow-hover:10px 10px 22px #c0c8d0,-10px -10px 22px #fff;
  --shadow-small:5px 5px 12px #c7cfd7,-5px -5px 12px #fbfdff;
  --shadow-inset:inset 3px 3px 7px #c8d0d8,inset -3px -3px 7px #f8fbfe;
}
body[data-theme="glass"]{
  --bg:#dfeaf2;--panel:rgba(235,244,249,.86);--soft:rgba(216,229,238,.72);
  --line:rgba(117,145,166,.18);--text:#102b45;--muted:#617a91;
  --primary:#2f6f9f;--primary-hover:#245c86;--active:#d6e7f8;
  --input:rgba(245,250,253,.66);--ok:#27785d;--bad:#a44d55;
  --shadow:8px 9px 20px rgba(105,132,151,.18),-5px -5px 13px rgba(255,255,255,.72);
  --shadow-hover:10px 12px 24px rgba(95,123,143,.22),-5px -5px 15px rgba(255,255,255,.78);
  --shadow-small:5px 6px 13px rgba(105,132,151,.16),-3px -3px 9px rgba(255,255,255,.68);
  --shadow-inset:inset 2px 2px 5px rgba(117,145,166,.16),inset -2px -2px 5px rgba(255,255,255,.52);
}
body{background:var(--bg);color:var(--text);padding:32px;transition:background var(--ease),color var(--ease)}
body[data-theme="glass"]:before{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 14% 18%,rgba(255,255,255,.55),transparent 34%),radial-gradient(circle at 84% 76%,rgba(146,181,204,.22),transparent 36%)}
.shell{position:relative;z-index:1;max-width:1120px;margin:0 auto}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding:4px 6px;gap:16px}
.brand{display:flex;align-items:center;gap:14px}
.mark{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;background:var(--panel);box-shadow:var(--shadow-small);font-family:Georgia,serif;font-size:21px;font-weight:700;letter-spacing:-1px}
.brand h1{font-family:Georgia,"Noto Serif SC",serif;font-size:25px;line-height:1;margin:0 0 7px;letter-spacing:-.4px}
.brand p{margin:0;color:var(--muted);font-size:13px}
.top-actions{display:flex;align-items:center;gap:10px;flex:0 0 auto}
.theme-switch,.settings-button{white-space:nowrap;border:1px solid var(--line);background:var(--panel);color:var(--text);box-shadow:var(--shadow-small);border-radius:999px;padding:10px 15px;cursor:pointer;transition:box-shadow var(--ease),transform var(--ease)}
.theme-switch:hover{box-shadow:var(--shadow-hover)}
.settings-button:hover{box-shadow:var(--shadow-hover)}
.theme-switch:active{box-shadow:var(--shadow-inset);transform:translateY(1px)}
.settings-button:active{box-shadow:var(--shadow-inset);transform:translateY(1px)}
.workspace{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr);gap:24px;align-items:start}
.right-stack{display:grid;gap:18px;min-width:0}
.surface{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius-xl);box-shadow:var(--shadow);padding:28px;transition:background var(--ease),box-shadow var(--ease)}
body[data-theme="glass"] .surface{backdrop-filter:blur(16px) saturate(115%);-webkit-backdrop-filter:blur(16px) saturate(115%)}
.eyebrow{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px}
.eyebrow:before{content:"";width:24px;height:2px;border-radius:2px;background:var(--primary)}
h2{font-family:Georgia,"Noto Serif SC",serif;font-size:29px;line-height:1.28;margin:0 0 10px;letter-spacing:-.5px}
.lead{margin:0 0 24px;color:var(--muted);line-height:1.75;font-size:14px}
label{display:block;font-size:13px;font-weight:700;margin-bottom:9px}
textarea,input,select{width:100%;border:1px solid var(--line);background:var(--input);color:var(--text);border-radius:var(--radius-md);outline:none;box-shadow:var(--shadow-inset);transition:border-color var(--ease),box-shadow var(--ease);font:inherit}
textarea{min-height:218px;padding:17px;resize:vertical;line-height:1.72}
input,select{height:46px;padding:0 13px}
textarea:focus,input:focus,select:focus{border-color:#6f9ab8;box-shadow:var(--shadow-inset),0 0 0 3px rgba(75,129,168,.15)}
textarea::placeholder,input::placeholder{color:#8092a2}
.settings{display:grid;grid-template-columns:minmax(220px,1fr) 160px 190px;gap:14px;padding:2px 14px 14px}
.settings-dialog{width:min(460px,calc(100vw - 32px));max-width:none;max-height:min(88vh,640px);overflow:auto;border:1px solid var(--line);border-radius:24px;background:var(--panel);color:var(--text);padding:24px;box-shadow:var(--shadow-hover)}
.settings-dialog::backdrop{background:rgba(22,34,46,.30);backdrop-filter:blur(3px)}
.settings-dialog[open]{animation:modal-in 150ms ease-out}
.dialog-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:22px}
.dialog-heading h2{font-size:23px;margin:0}
.dialog-heading p{margin:0 0 7px;color:var(--muted);font-size:12px}
.settings-dialog .settings{grid-template-columns:1fr;gap:16px;padding:0}
.settings-dialog .settings-note{margin:18px 0 0;padding:0;color:var(--muted);font-size:12px;line-height:1.7}
.dialog-actions{display:flex;justify-content:flex-end;margin-top:22px}
.dialog-close,.dialog-done{border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--text);padding:9px 15px;cursor:pointer;box-shadow:var(--shadow-small);font:inherit}
.dialog-close{width:36px;height:36px;padding:0;font-size:20px;line-height:1}
.dialog-done{min-width:92px;font-weight:700}
.primary{width:100%;height:52px;margin-top:20px;border:0;border-radius:16px;background:var(--primary);color:#f7fafc;font-size:15px;font-weight:800;letter-spacing:.04em;cursor:pointer;box-shadow:0 10px 22px rgba(38,52,66,.2);transition:background var(--ease),transform var(--ease),box-shadow var(--ease)}
.primary:hover{background:var(--primary-hover);transform:translateY(-1px);box-shadow:0 12px 26px rgba(38,52,66,.25)}
.primary:active{transform:translateY(1px);box-shadow:0 5px 12px rgba(38,52,66,.22)}
.primary:disabled{cursor:not-allowed;opacity:.58;transform:none;box-shadow:none}
.privacy{display:flex;gap:10px;margin-top:16px;color:var(--muted);font-size:12px;line-height:1.65}
.shield{flex:0 0 25px;height:25px;border-radius:9px;display:grid;place-items:center;background:var(--active);font-size:12px}
.settings-note{margin:2px 0 0;padding:0 14px 14px;color:var(--muted);font-size:11px;line-height:1.65}
.waiting-card,.queue-card,.history-card{padding:22px 24px}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.panel-title{font-size:16px;font-weight:800;margin:0}.panel-sub{font-size:12px;color:var(--muted);margin:6px 0 0;line-height:1.55}
.count-badge{min-width:42px;height:34px;padding:0 10px;display:grid;place-items:center;border-radius:12px;background:var(--active);color:var(--text);font-size:18px;font-weight:800;box-shadow:var(--shadow-small)}
.queue-list,.history-list{display:flex;flex-direction:column;gap:9px;margin-top:15px;max-height:220px;overflow:auto;padding:2px 4px 2px 1px}
.task-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid var(--line);border-radius:13px;background:var(--soft);font-size:12px;line-height:1.45}
.task-main{min-width:0}.task-title{display:block;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-meta{display:block;color:var(--muted);margin-top:3px;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-state{flex:0 0 auto;color:var(--muted);font-size:11px}.task-state.ok{color:var(--ok)}.task-state.fail{color:var(--bad)}
.panel-empty{padding:13px 4px 2px;color:var(--muted);font-size:12px}
.status-card{min-height:420px;display:flex;flex-direction:column}
.status-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.state-dot{width:11px;height:11px;border-radius:999px;background:#8da0af;box-shadow:0 0 0 6px rgba(141,160,175,.12);margin-top:6px;transition:background var(--ease)}
.state-dot.running{background:#477b9d;animation:pulse 1.8s infinite}
.state-dot.done{background:var(--ok);box-shadow:0 0 0 6px rgba(47,123,98,.12)}
.state-dot.error{background:var(--bad);box-shadow:0 0 0 6px rgba(169,80,85,.12)}
.status-title{font-size:17px;font-weight:800;margin:0}.status-sub{font-size:12px;color:var(--muted);margin:6px 0 0}
.progress-wrap{margin:24px 0 18px}.progress-track{height:9px;border-radius:999px;background:var(--soft);box-shadow:var(--shadow-inset);overflow:hidden}
.progress-bar{height:100%;width:0;background:linear-gradient(90deg,#426f8d,#6b91aa);border-radius:inherit;transition:width 520ms ease}
.progress-bar.active{width:38%;animation:travel 1.1s ease-in-out infinite}
.progress-meta{display:flex;justify-content:space-between;margin-top:9px;color:var(--muted);font-size:12px}
.empty{margin:auto 0;text-align:center;color:var(--muted);padding:34px 16px}
.empty-symbol{width:72px;height:72px;border-radius:24px;margin:0 auto 18px;display:grid;place-items:center;background:var(--panel);box-shadow:var(--shadow-small);font-family:Georgia,serif;font-size:28px;color:#6d8192}
.empty strong{display:block;color:var(--text);font-size:14px;margin-bottom:8px}
.results{display:none;gap:10px;flex-direction:column;max-height:330px;overflow:auto;padding:4px 5px 4px 2px}
.results.show{display:flex}.result{padding:13px 14px;border-radius:14px;background:var(--soft);border:1px solid var(--line);font-size:13px;line-height:1.55}
.result-top{display:flex;justify-content:space-between;gap:10px}.result-name{font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.result-count{white-space:nowrap;color:var(--muted);font-size:12px}
.result.ok{border-left:3px solid var(--ok)}.result.fail{border-left:3px solid var(--bad)}
.result-error{color:var(--bad);font-size:12px;margin-top:4px}
.footnote{text-align:center;color:var(--muted);font-size:11px;margin-top:22px;line-height:1.7}
button:focus-visible,textarea:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid rgba(47,111,159,.32);outline-offset:3px}
@keyframes pulse{0%,100%{box-shadow:0 0 0 5px rgba(71,123,157,.13)}50%{box-shadow:0 0 0 10px rgba(71,123,157,.04)}}
@keyframes travel{0%{transform:translateX(-110%)}50%{transform:translateX(80%)}100%{transform:translateX(280%)}}
@keyframes modal-in{from{opacity:0;transform:translateY(8px) scale(.985)}to{opacity:1;transform:translateY(0) scale(1)}}
@media(max-width:760px){body{padding:18px 14px}.workspace{grid-template-columns:1fr}.surface{padding:20px;border-radius:22px}.settings{grid-template-columns:1fr}.topbar{align-items:flex-start}.brand p{max-width:210px}.status-card{min-height:330px}}
@media(max-width:480px){.topbar{gap:10px}.brand{min-width:0;gap:10px}.brand p{display:none}.mark{width:40px;height:40px;border-radius:13px;font-size:18px}.brand h1{font-size:22px;margin:9px 0 0}.theme-switch,.settings-button{padding:9px 11px;font-size:12px}.surface{padding:18px}textarea{min-height:190px}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){body[data-theme="glass"] .surface{background:#edf4f8}}
</style>
</head>
<body data-theme="neo">
<main class="shell">
  <header class="topbar">
    <div class="brand"><div class="mark">∞</div><div><h1>__APP_NAME__</h1><p>多平台公开媒体 · 本地保存 · 无需登录</p></div></div>
    <div class="top-actions"><button class="settings-button" id="settingsButton" type="button" aria-haspopup="dialog" aria-controls="settingsDialog">设置</button><button class="theme-switch" id="themeButton" type="button" aria-label="切换视觉主题">玻璃主题</button></div>
  </header>
  <section class="workspace">
    <div class="surface">
      <div class="eyebrow">Original media</div>
      <h2>粘贴链接，保存原图。</h2>
      <p class="lead">复制小红书或抖音分享内容到下面，点一次即可。默认保存到电脑的“下载”文件夹。</p>
      <label for="input">分享文本或链接</label>
      <textarea id="input" placeholder="例如：复制小红书或抖音分享文本到这里，也可以一次粘贴多条链接。"></textarea>
      <button class="primary" id="go" type="button">开始下载</button>
      <div class="privacy"><span class="shield">✓</span><span>公开笔记无需账号、密码或 Cookie。链接默认只交给本机引擎，不会静默发送到在线解析网站。</span></div>
    </div>
    <aside class="right-stack" aria-live="polite">
      <section class="surface waiting-card">
        <div class="panel-head"><div><p class="panel-title">等待任务</p><p class="panel-sub" id="waitingSub">当前没有排队的下载</p></div><span class="count-badge" id="waitingCount">0</span></div>
      </section>
      <section class="surface status-card">
        <div class="status-head"><div><p class="status-title" id="statusTitle">正在进行的任务</p><p class="status-sub" id="statusSub">还没有开始下载</p></div><span class="state-dot" id="stateDot"></span></div>
        <div class="progress-wrap"><div class="progress-track"><div class="progress-bar" id="progressBar"></div></div><div class="progress-meta"><span id="progressText">0 / 0</span><span id="successText">成功 0</span></div></div>
        <div class="empty" id="empty"><div class="empty-symbol">↓</div><strong>结果会在这里逐条出现</strong><span>关闭页面不会删除已经保存到本地的文件。</span></div>
        <div class="results" id="results"></div>
      </section>
      <section class="surface queue-card">
        <div class="panel-head"><div><p class="panel-title">排队任务</p><p class="panel-sub" id="queueSub">读取本机下载队列和剪贴板队列</p></div></div>
        <div class="queue-list" id="queueList"><div class="panel-empty">暂无排队任务</div></div>
      </section>
      <section class="surface history-card">
        <div class="panel-head"><div><p class="panel-title">历史下载记录</p><p class="panel-sub" id="historySub">正在读取本机下载档案</p></div></div>
        <div class="history-list" id="historyList"><div class="panel-empty">暂无历史记录</div></div>
      </section>
    </aside>
  </section>
  <p class="footnote">仅处理你有权保存的公开内容 · 创作者嵌入原图的署名会保留 · __APP_NAME__ V__APP_VERSION__</p>
</main>
<dialog class="settings-dialog" id="settingsDialog" aria-labelledby="settingsTitle">
  <div class="dialog-heading"><div><p>本机下载偏好</p><h2 id="settingsTitle">下载设置</h2></div><button class="dialog-close" id="settingsClose" type="button" aria-label="关闭设置">×</button></div>
  <div class="settings">
    <div><label for="outdir">保存位置</label><input id="outdir" type="text" autocomplete="off"></div>
    <div><label for="mode">下载节奏</label><select id="mode"><option value="auto" selected>智能 · 随结果调节</option><option value="fast">快速 · 3–8 秒</option><option value="normal">标准 · 8–15 秒</option><option value="cautious">稳妥 · 35–55 秒</option><option value="slow">慢速 · 55–85 秒</option><option value="very-slow">极慢 · 110–160 秒</option></select></div>
    <div><label for="format">图片格式</label><select id="format"><option value="keep" selected>保持原格式（推荐）</option><option value="jpg">JPG</option><option value="png">PNG（无损）</option></select></div>
  </div>
  <p class="settings-note">修改后会自动保存在本机。其他本机软件也可调用 <code>POST /api/v1/jobs</code>；<a href="/api/openapi.json" target="_blank" rel="noreferrer">查看接口规范</a>。</p>
  <div class="dialog-actions"><button class="dialog-done" id="settingsDone" type="button">完成</button></div>
</dialog>
<script>
const THEME_KEY='xhs-dl-theme',OUTPUT_KEY='xhs-dl-output',MODE_KEY='xhs-dl-mode',FORMAT_KEY='xhs-dl-format',DEFAULT_OUTPUT=__DEFAULT_OUTPUT_JSON__,MIN_PROGRESS_MS=1100;
const $=id=>document.getElementById(id);let activeJob=null,pollTimer=null,jobStartedAt=0;
function applyTheme(theme){const next=theme==='glass'?'glass':'neo';document.body.dataset.theme=next;localStorage.setItem(THEME_KEY,next);$('themeButton').textContent=next==='neo'?'玻璃主题':'拟态主题'}
applyTheme(localStorage.getItem(THEME_KEY)||'neo');
$('themeButton').addEventListener('click',()=>applyTheme(document.body.dataset.theme==='neo'?'glass':'neo'));
const settingsDialog=$('settingsDialog');
$('settingsButton').addEventListener('click',()=>settingsDialog.showModal());
$('settingsClose').addEventListener('click',()=>settingsDialog.close());
$('settingsDone').addEventListener('click',()=>settingsDialog.close());
settingsDialog.addEventListener('click',event=>{if(event.target===settingsDialog)settingsDialog.close()});
$('outdir').value=localStorage.getItem(OUTPUT_KEY)||DEFAULT_OUTPUT;
if(localStorage.getItem(MODE_KEY)==='cautious')localStorage.setItem(MODE_KEY,'auto');
if(localStorage.getItem(FORMAT_KEY)==='jpg')localStorage.setItem(FORMAT_KEY,'keep');
$('mode').value=localStorage.getItem(MODE_KEY)||'auto';$('format').value=localStorage.getItem(FORMAT_KEY)||'keep';
$('outdir').addEventListener('change',e=>localStorage.setItem(OUTPUT_KEY,e.target.value.trim()));$('mode').addEventListener('change',e=>localStorage.setItem(MODE_KEY,e.target.value));$('format').addEventListener('change',e=>localStorage.setItem(FORMAT_KEY,e.target.value));
function setState(status,title,sub){$('stateDot').className='state-dot '+status;$('statusTitle').textContent=title;$('statusSub').textContent=sub}
function render(job){const total=job.total||0,done=job.done||0,success=job.success||0,running=job.status==='running'||job.status==='queued';$('progressBar').classList.toggle('active',running&&done===0);if(!(running&&done===0)){$('progressBar').style.transform='none';$('progressBar').style.width=(total?Math.round(done/total*100):0)+'%'}$('progressText').textContent=`${done} / ${total}`;$('successText').textContent=`成功 ${success}`;
  const items=job.items||[];$('empty').style.display=items.length?'none':'block';$('results').classList.toggle('show',items.length>0);$('results').innerHTML='';items.forEach(it=>{const d=document.createElement('div');d.className='result '+(it.success?'ok':'fail');const top=document.createElement('div');top.className='result-top';const name=document.createElement('span');name.className='result-name';name.textContent=it.title||it.error||'未命名笔记';const count=document.createElement('span');count.className='result-count';count.textContent=it.success?`${it.image_success||0} 张`:'失败';top.append(name,count);d.append(top);if(!it.success&&it.error){const err=document.createElement('div');err.className='result-error';err.textContent=it.error;d.append(err)}$('results').append(d)});
  if(job.status==='queued')setState('running','等待执行',total?`排队中，共 ${total} 条`:'等待本地引擎');else if(job.status==='running')setState('running','正在逐条提取',total?`已完成 ${done} 条，共 ${total} 条`:'正在准备本地引擎');else if(job.status==='completed')setState(job.failed?'error':'done',job.failed?'任务完成，有失败项':'全部保存完成',`成功 ${job.success||0} 条，失败 ${job.failed||0} 条`);else if(job.status==='error')setState('error','任务没有完成',job.error||'请稍后重试')}
function renderRows(target,list,kind){target.innerHTML='';if(!list||!list.length){const empty=document.createElement('div');empty.className='panel-empty';empty.textContent=kind==='history'?'还没有本地成功下载记录':'当前队列为空';target.append(empty);return}list.forEach(job=>{const row=document.createElement('div');row.className='task-row';const main=document.createElement('div');main.className='task-main';const title=document.createElement('span');title.className='task-title';const first=(job.items||[])[0];title.textContent=job.title||job.title_hint||(first&&first.title)||(job.url||`任务 ${String(job.job_id||'').slice(0,8)}`);const meta=document.createElement('span');meta.className='task-meta';if(kind==='history'){const parts=[];if(job.completed_at)parts.push(job.completed_at);if(job.note_id)parts.push(`笔记 ${job.note_id}`);meta.textContent=parts.join(' · ')||job.url||'旧记录未保存时间'}else if(job.note_id)meta.textContent=`笔记 ${job.note_id}`;else if(job.retry_count)meta.textContent=`${job.url||''} · 已重试 ${job.retry_count} 次`;else if(job.url)meta.textContent=job.url;else meta.textContent=`${job.done||0} / ${job.total||0} 条 · 成功 ${job.success||0}`;main.append(title,meta);const state=document.createElement('span');const status=job.status||'';const ok=kind==='history'||status==='completed'||status==='success';const failed=status==='error'||status==='failed';state.className='task-state '+(ok?'ok':failed?'fail':'');state.textContent=kind==='history'?'已保存':status==='running'?'进行中':status==='cooling_down'?'冷却中':failed?'失败':'等待';row.append(main,state);target.append(row)})}
async function refreshDashboard(){try{const r=await fetch('/api/v1/jobs?limit=50');if(!r.ok)return;const data=await r.json();const counts=data.counts||{},collector=data.collector||{};const waiting=data.waiting||[];const queue=data.queue||waiting;const running=data.running||[];$('waitingCount').textContent=counts.waiting??waiting.length;$('waitingSub').textContent=waiting.length?`有 ${waiting.length} 条任务等待 · 剪贴板 ${collector.pending_count||0} 条`:'当前队列为空 · 剪贴板待采集 0 条';$('queueSub').textContent=`剪贴板队列 ${collector.pending_count||0} 条 · 失败归档 ${collector.failed_archive_count||0} 条（不在等待队列）`;$('historySub').textContent=`本机下载成功 ${counts.download_history||0} 条 · 剪贴板成功 ${collector.history_count||0} 条`;renderRows($('queueList'),queue,'queue');renderRows($('historyList'),data.history||[],'history');if(activeJob)return;if(running.length){const current=running[0];if(current.source==='clipboard'){setState('running','剪贴板正在采集',current.title||current.url||'正在处理当前链接');$('progressBar').classList.add('active');$('progressText').textContent='采集进行中';$('successText').textContent='';$('empty').style.display='none';$('results').classList.remove('show')}else setState('running','正在逐条提取',`任务进行中，共 ${current.total||0} 条`);return}if(collector.status==='offline'){setState('error','剪贴板采集器离线',collector.last_heartbeat?`最近心跳：${collector.last_heartbeat}`:'没有可用心跳');$('progressBar').classList.remove('active')}else if(collector.status==='paused'){setState('','剪贴板采集已暂停',collector.pending_count?`仍有 ${collector.pending_count} 条等待恢复`:'当前没有等待任务');$('progressBar').classList.remove('active')}else if(collector.status==='cooling'){setState('running','采集器冷却中',collector.cooldown_remaining_seconds?`约 ${collector.cooldown_remaining_seconds} 秒后继续 · ${collector.cooldown_reason||'按限速策略等待'}`:'按限速策略等待');$('progressBar').classList.add('active')}else{setState('done','当前没有进行中的下载',collector.status==='idle'?'下载器已就绪，采集器空闲':'等待任务启动');$('progressBar').classList.remove('active')}}catch(_){}}
function finish(){activeJob=null;$('go').disabled=false;$('go').textContent='开始下载';refreshDashboard()}
async function poll(){if(!activeJob)return;try{const r=await fetch('/api/jobs/'+activeJob);const job=await r.json();if(!r.ok)throw new Error(job.error||'读取任务失败');if(job.status==='completed'||job.status==='error'){const wait=Math.max(0,MIN_PROGRESS_MS-(Date.now()-jobStartedAt));if(wait){pollTimer=setTimeout(()=>{render(job);finish()},wait);return}render(job);finish();return}render(job);refreshDashboard();pollTimer=setTimeout(poll,700)}catch(e){setState('error','连接中断',e.message);$('progressBar').classList.remove('active');$('go').disabled=false;$('go').textContent='重新开始';activeJob=null}}
async function start(){if(activeJob)return;const text=$('input').value.trim();if(!text){$('input').focus();setState('error','还缺少分享文本','请先粘贴至少一条公开媒体链接');return}const output_dir=$('outdir').value.trim()||DEFAULT_OUTPUT,mode=$('mode').value,image_format=$('format').value;localStorage.setItem(OUTPUT_KEY,output_dir);localStorage.setItem(MODE_KEY,mode);localStorage.setItem(FORMAT_KEY,image_format);jobStartedAt=Date.now();$('go').disabled=true;$('go').textContent='正在准备…';$('progressBar').classList.add('active');$('progressBar').style.width='38%';$('progressText').textContent='准备中';$('successText').textContent='';$('results').innerHTML='';$('results').classList.remove('show');$('empty').style.display='block';setState('running','正在准备','连接本地无水印引擎');try{const r=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,output_dir,mode,image_format})});const data=await r.json();if(!r.ok)throw new Error(data.error||'创建任务失败');activeJob=data.job_id;$('go').textContent='下载进行中';poll()}catch(e){$('progressBar').classList.remove('active');setState('error','无法开始',e.message);$('go').disabled=false;$('go').textContent='重新开始'}}
$('go').addEventListener('click',start);$('input').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')start()});refreshDashboard();setInterval(refreshDashboard,2500);
</script>
</body>
</html>"""


def _item_payload(item):
    return {
        "success": item.success,
        "title": item.title,
        "error": item.error,
        "image_count": item.image_count,
        "image_success": item.image_success,
        "save_dir": item.save_dir,
        "note_id": item.note_id,
    }


def _job_summary(job):
    """Return the small, safe shape used by the queue and history panels."""
    return {
        "job_id": job.get("job_id", ""),
        "status": job.get("status", ""),
        "created_at": job.get("created_at", 0),
        "finished_at": job.get("finished_at", 0),
        "total": job.get("total", 0),
        "done": job.get("done", 0),
        "success": job.get("success", 0),
        "failed": job.get("failed", 0),
        "output_dir": job.get("output_dir", ""),
        "error": job.get("error", ""),
        "items": [
            {
                "success": item.get("success", False),
                "title": item.get("title", ""),
                "error": item.get("error", ""),
                "image_success": item.get("image_success", 0),
            }
            for item in (job.get("items") or [])[-8:]
            if isinstance(item, dict)
        ],
    }


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _collector_snapshot():
    queue_data = _read_json(CLIPBOARD_QUEUE_FILE, {})
    heartbeat = _read_json(COLLECTOR_HEARTBEAT_FILE, {})
    clipboard_history = _read_json(CLIPBOARD_HISTORY_FILE, {})
    queue = queue_data.get("queue", []) if isinstance(queue_data, dict) else []
    failed = queue_data.get("failed", []) if isinstance(queue_data, dict) else []
    queue = [item for item in queue if isinstance(item, dict)] if isinstance(queue, list) else []
    failed = [item for item in failed if isinstance(item, dict)] if isinstance(failed, list) else []

    timestamp = heartbeat.get("timestamp") if isinstance(heartbeat, dict) else None
    try:
        age = max(0.0, time.time() - float(timestamp))
    except (TypeError, ValueError):
        age = None
    pid = heartbeat.get("pid") if isinstance(heartbeat, dict) else None
    fresh = age is not None and age <= 45.0 and bool(pid)
    raw_extra = heartbeat.get("extra", "") if isinstance(heartbeat, dict) else ""
    extra = {}
    if isinstance(raw_extra, dict):
        extra = raw_extra
    elif isinstance(raw_extra, str) and raw_extra.lstrip().startswith("{"):
        try:
            parsed = json.loads(raw_extra)
            if isinstance(parsed, dict):
                extra = parsed
        except ValueError:
            pass

    current_url = str(extra.get("current_url") or "")
    current_title = str(extra.get("current_title") or "")
    current = None
    if fresh and heartbeat.get("status") == "downloading":
        matched = next((item for item in queue if item.get("url") == current_url), None)
        if matched is None and queue:
            matched = queue[0]
        if matched:
            current = {
                "job_id": matched.get("id", ""),
                "title": current_title or matched.get("title_hint") or "正在采集",
                "url": matched.get("url", ""),
                "status": "running",
                "source": "clipboard",
                "retry_count": matched.get("retry_count", 0),
            }
            queue = [item for item in queue if item.get("id") != matched.get("id")]
    elif fresh and current_url:
        current = {
            "job_id": "clipboard-current",
            "title": current_title or heartbeat.get("extra", "剪贴板采集任务"),
            "url": current_url,
            "status": "running",
            "source": "clipboard",
        }

    try:
        remaining = max(0, float(queue_data.get("cooldown_until", 0) or 0) - time.time()) if isinstance(queue_data, dict) else 0
    except (TypeError, ValueError):
        remaining = 0
    paused = fresh and heartbeat.get("status") == "paused"
    if not fresh:
        status = "offline"
    elif paused:
        status = "paused"
    elif heartbeat.get("status") == "cooling" or remaining > 0:
        status = "cooling"
    elif current:
        status = "downloading"
    else:
        status = "idle"

    urls = clipboard_history.get("urls", []) if isinstance(clipboard_history, dict) else []
    return {
        "status": status,
        "online": fresh,
        "paused": paused,
        "heartbeat_age_seconds": round(age, 1) if age is not None else None,
        "last_heartbeat": heartbeat.get("last_heartbeat", "") if isinstance(heartbeat, dict) else "",
        "pid": pid,
        "current": current,
        "pending": [
            {
                "job_id": item.get("id", ""),
                "title": item.get("title_hint") or "剪贴板采集任务",
                "url": item.get("url", ""),
                "status": item.get("status", "pending"),
                "source": "clipboard",
                "retry_count": item.get("retry_count", 0),
                "last_error": item.get("last_error") or "",
            }
            for item in queue[:MAX_DASHBOARD_ROWS]
        ],
        "pending_count": len(queue),
        "failed_archive_count": len(failed),
        "history_count": len(urls) if isinstance(urls, list) else 0,
        "cooldown_remaining_seconds": round(remaining),
        "cooldown_reason": str(queue_data.get("cooldown_reason", "") or "") if isinstance(queue_data, dict) else "",
    }


def _download_history(limit=MAX_DASHBOARD_ROWS):
    entries = _read_json(history_path(), [])
    if not isinstance(entries, list):
        return [], 0
    rows = []
    for item in reversed(entries):
        if not isinstance(item, dict):
            continue
        url = item.get("下载网址") or item.get("url") or ""
        rows.append(
            {
                "job_id": item.get("笔记ID") or url,
                "note_id": item.get("笔记ID") or "",
                "title": item.get("标题") or "未命名作品",
                "url": url,
                "completed_at": item.get("下载时间") or item.get("completed_at") or "",
                "status": "completed",
                "source": "downloader-history",
            }
        )
    return rows[:limit], len(rows)


def _dashboard_payload(limit=50):
    with JOBS_LOCK:
        current_jobs = [copy.deepcopy(value) for value in JOBS.values()]
    current_jobs.sort(key=lambda item: item.get("created_at", 0))
    web_waiting = [
        {**_job_summary(job), "source": "web"}
        for job in current_jobs
        if job.get("status") == "queued"
    ]
    web_running = [
        {**_job_summary(job), "source": "web"}
        for job in current_jobs
        if job.get("status") == "running"
    ]
    with WEB_HISTORY_LOCK:
        web_history = copy.deepcopy(list(reversed(WEB_HISTORY[-limit:])))

    collector = _collector_snapshot()
    downloads, download_count = _download_history(limit)
    clipboard_waiting = collector["pending"]
    waiting = web_waiting + clipboard_waiting
    running = web_running + ([collector["current"]] if collector["current"] else [])
    return {
        "waiting": waiting,
        "running": running,
        "queue": waiting,
        "history": downloads,
        "web_history": web_history,
        "collector": collector,
        "counts": {
            "waiting": len(waiting),
            "running": len(running),
            "history": download_count,
            "download_history": download_count,
            "web_history": len(WEB_HISTORY),
            "clipboard_history": collector["history_count"],
            "clipboard_failed_archive": collector["failed_archive_count"],
        },
        "history_limit": limit,
    }


def _openapi_document():
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "万能下载器本地 API",
            "version": __version__,
            "description": "供本机 AI、脚本和桌面应用提交公开媒体下载任务并读取真实进度。默认只监听本机回环地址。",
        },
        "servers": [{"url": "http://127.0.0.1:5678"}],
        "paths": {
            "/api/v1/capabilities": {
                "get": {
                    "summary": "读取下载器能力和默认设置",
                    "responses": {"200": {"description": "支持的平台、格式和接口信息", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Capabilities"}}}}},
                }
            },
            "/api/v1/health": {
                "get": {
                    "summary": "检查本地 API 是否可用",
                    "responses": {"200": {"description": "服务健康状态", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Health"}}}}},
                }
            },
            "/api/v1/jobs": {
                "get": {
                    "summary": "读取等待、进行中、剪贴板队列与本机成功历史",
                    "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}}],
                    "responses": {"200": {"description": "合并后的本机任务看板", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Dashboard"}}}}},
                },
                "post": {
                    "summary": "提交一个或多个公开媒体链接",
                    "parameters": [{"name": "Idempotency-Key", "in": "header", "required": False, "schema": {"type": "string", "maxLength": 128}, "description": "可选；同一服务进程内避免网络重试造成重复提交，保留 24 小时。"}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CreateJobRequest"},
                                "examples": {
                                    "url-list": {"value": {"urls": ["https://example.com/public-media"], "image_format": "keep", "mode": "auto"}},
                                    "share-text": {"value": {"text": "复制的分享文案和链接", "image_format": "keep", "mode": "auto"}},
                                },
                            }
                        },
                    },
                    "responses": {
                        "202": {"description": "已接收；使用响应中的 job_id 继续轮询任务状态。", "headers": {"Location": {"description": "任务状态资源路径。", "schema": {"type": "string"}}, "Retry-After": {"description": "建议轮询间隔，秒。", "schema": {"type": "integer"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AcceptedJob"}}}},
                        "200": {"description": "同一个幂等键已提交过，返回原任务。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AcceptedJob"}}}},
                        "400": {"description": "请求内容无效或未检测到链接。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}},
                        "409": {"description": "幂等键已用于不同的请求内容。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}},
                        "413": {"description": "请求文本超过 1 MiB 或单批超过 100 条链接。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}},
                    },
                },
            },
            "/api/v1/jobs/{job_id}": {
                "get": {
                    "summary": "轮询单个下载任务",
                    "parameters": [{"name": "job_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "任务进度和已完成条目", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/JobStatus"}}}}, "404": {"description": "任务不存在", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}}},
                }
            },
        },
        "components": {
            "schemas": {
                "CreateJobRequest": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "整段分享文案或一个/多个链接。"},
                        "urls": {"type": "array", "items": {"type": "string", "format": "uri"}, "maxItems": 100},
                        "output_dir": {"type": "string", "description": "本机保存目录；省略时使用下载文件夹。"},
                        "mode": {"type": "string", "enum": ["auto", "fast", "normal", "cautious", "slow", "very-slow"], "default": "auto"},
                        "image_format": {"type": "string", "enum": ["keep", "jpg", "png"], "default": "keep"},
                    },
                    "anyOf": [{"required": ["text"]}, {"required": ["urls"]}],
                },
                "AcceptedJob": {
                    "type": "object",
                    "required": ["job_id", "status", "total"],
                    "properties": {"job_id": {"type": "string"}, "status": {"type": "string", "enum": ["queued", "running", "completed", "error"]}, "total": {"type": "integer", "minimum": 0}, "deduplicated": {"type": "boolean"}},
                },
                "JobStatus": {
                    "type": "object",
                    "required": ["job_id", "status", "total"],
                    "properties": {
                        "job_id": {"type": "string"}, "status": {"type": "string", "enum": ["queued", "running", "completed", "error"]},
                        "created_at": {"type": "number"}, "finished_at": {"type": "number"}, "total": {"type": "integer", "minimum": 0},
                        "done": {"type": "integer", "minimum": 0}, "success": {"type": "integer", "minimum": 0}, "failed": {"type": "integer", "minimum": 0},
                        "items": {"type": "array", "items": {"type": "object", "additionalProperties": True}}, "error": {"type": "string"}, "output_dir": {"type": "string"},
                    },
                },
                "TaskSummary": {
                    "type": "object", "additionalProperties": True,
                    "properties": {"job_id": {"type": "string"}, "title": {"type": "string"}, "url": {"type": "string"}, "status": {"type": "string"}, "source": {"type": "string"}, "completed_at": {"type": "string"}},
                },
                "Dashboard": {
                    "type": "object",
                    "required": ["waiting", "running", "queue", "history", "collector", "counts"],
                    "properties": {
                        "waiting": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "running": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "queue": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "history": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "web_history": {"type": "array", "items": {"$ref": "#/components/schemas/JobStatus"}},
                        "collector": {"type": "object", "additionalProperties": True},
                        "counts": {"type": "object", "properties": {"waiting": {"type": "integer"}, "running": {"type": "integer"}, "history": {"type": "integer"}, "download_history": {"type": "integer"}, "web_history": {"type": "integer"}, "clipboard_history": {"type": "integer"}, "clipboard_failed_archive": {"type": "integer"}}, "additionalProperties": True},
                        "history_limit": {"type": "integer"},
                    },
                },
                "Capabilities": {
                    "type": "object", "required": ["api_version", "transport", "endpoints"],
                    "properties": {"name": {"type": "string"}, "version": {"type": "string"}, "api_version": {"type": "string"}, "transport": {"type": "string"}, "auth": {"type": "string"}, "platforms": {"type": "array", "items": {"type": "string"}}, "image_formats": {"type": "array", "items": {"type": "string"}}, "default_image_format": {"type": "string"}, "default_mode": {"type": "string"}, "endpoints": {"type": "object", "additionalProperties": {"type": "string"}}},
                },
                "Health": {"type": "object", "required": ["status", "name", "version"], "properties": {"status": {"type": "string"}, "name": {"type": "string"}, "version": {"type": "string"}}},
                "ApiError": {"type": "object", "required": ["error"], "properties": {"error": {"type": "string"}, "supported_modes": {"type": "array", "items": {"type": "string"}}}},
            }
        },
    }


def _save_web_history():
    with WEB_HISTORY_LOCK:
        snapshot = copy.deepcopy(WEB_HISTORY[-100:])
    try:
        WEB_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = WEB_HISTORY_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(WEB_HISTORY_FILE)
    except OSError:
        # Download results should never fail because the optional UI history
        # file is unavailable or read-only.
        pass


def _record_web_history(job):
    if not job:
        return
    summary = _job_summary(job)
    with WEB_HISTORY_LOCK:
        WEB_HISTORY[:] = [
            value for value in WEB_HISTORY if value.get("job_id") != summary["job_id"]
        ]
        WEB_HISTORY.append(summary)
        del WEB_HISTORY[:-100]
    _save_web_history()


def _update_job(job_id, **values):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)


def _run_job(job_id, urls, output_dir, delay, image_format, adaptive=False):
    # Run one download job at a time.  This keeps the original UI's queue
    # meaningful and avoids turning a burst of pasted links into concurrent
    # requests against a public platform.
    with JOB_CONDITION:
        while True:
            job = JOBS.get(job_id)
            if job is None:
                return
            running = any(
                value.get("status") == "running"
                for key, value in JOBS.items()
                if key != job_id
            )
            if not running:
                job["status"] = "running"
                break
            JOB_CONDITION.wait(timeout=0.5)

    def on_progress(item, index, total):
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["items"].append(_item_payload(item))
            job["done"] = index
            job["success"] = sum(1 for value in job["items"] if value["success"])
            job["failed"] = index - job["success"]

    try:
        downloader = UnifiedDownloader(
            output_dir=output_dir,
            delay=delay,
            on_progress=on_progress,
            image_format=image_format,
            adaptive=adaptive,
        )
        result = downloader.download(urls)
        _update_job(
            job_id,
            status="completed",
            finished_at=time.time(),
            done=result.total,
            success=result.success_count,
            failed=result.fail_count,
            output_dir=result.output_dir,
        )
    except Exception as exc:
        _update_job(job_id, status="error", finished_at=time.time(), error=str(exc))
    finally:
        with JOBS_LOCK:
            finished = copy.deepcopy(JOBS.get(job_id))
        if finished and finished.get("status") in {"completed", "error"}:
            _record_web_history(finished)
        with JOB_CONDITION:
            JOB_CONDITION.notify_all()


class Handler(BaseHTTPRequestHandler):
    """HTTP 请求处理。"""

    def _api_path(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/v1/"):
            return "/api/" + path[len("/api/v1/"):]
        return path

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = self._api_path()
        if path in ("/", "/index.html"):
            html = TEMPLATE.replace(
                "__DEFAULT_OUTPUT_JSON__",
                json.dumps(DEFAULT_OUTPUT_DIR, ensure_ascii=False),
            ).replace("__APP_VERSION__", __version__).replace("__APP_NAME__", APP_NAME)
            self._html(html)
            return
        if path == "/api/openapi.json":
            self._json(_openapi_document())
            return
        if path == "/api/health":
            self._json({"status": "ok", "name": APP_NAME, "version": __version__})
            return
        if path == "/api/capabilities":
            self._json(
                {
                    "name": APP_NAME,
                    "version": __version__,
                    "api_version": "v1",
                    "transport": "local-http",
                    "auth": "local-only; service binds to loopback",
                    "platforms": ["xiaohongshu", "douyin", "public-media"],
                    "image_formats": ["keep", "jpg", "png"],
                    "default_image_format": "keep",
                    "default_mode": "auto",
                    "endpoints": {
                        "submit": "POST /api/v1/jobs",
                        "job": "GET /api/v1/jobs/<job_id>",
                        "dashboard": "GET /api/v1/jobs",
                        "openapi": "GET /api/openapi.json",
                    },
                }
            )
            return
        if path == "/api/jobs":
            query = {}
            try:
                query = dict(part.split("=", 1) if "=" in part else (part, "") for part in parsed.query.split("&") if part)
                limit = max(1, min(int(query.get("limit", 50)), MAX_DASHBOARD_ROWS))
            except (TypeError, ValueError):
                limit = 50
            self._json(_dashboard_payload(limit))
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = copy.deepcopy(JOBS.get(job_id))
            if job is None:
                with WEB_HISTORY_LOCK:
                    job = copy.deepcopy(next((value for value in WEB_HISTORY if value.get("job_id") == job_id), None))
            if job is None:
                self._json({"error": "任务不存在"}, 404)
            else:
                self._json(job)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self._api_path() != "/api/jobs":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 1024 * 1024:
                self._json({"error": "粘贴内容过大，请分批处理"}, 413)
                return
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json({"error": "请求格式无效"}, 400)
            return

        if not isinstance(body, dict):
            self._json({"error": "请求内容必须是 JSON 对象"}, 400)
            return
        text = body.get("text", "")
        supplied_urls = body.get("urls")
        if not isinstance(text, str):
            self._json({"error": "text 必须是字符串"}, 400)
            return
        if supplied_urls is not None:
            if not isinstance(supplied_urls, list) or not all(isinstance(url, str) for url in supplied_urls):
                self._json({"error": "urls 必须是字符串数组"}, 400)
                return
            if len(supplied_urls) > MAX_URLS_PER_JOB:
                self._json({"error": f"单批最多提交 {MAX_URLS_PER_JOB} 条链接"}, 413)
                return
            text = "\n".join([text, *supplied_urls])
        urls = extract_urls_from_text(text)
        if not urls:
            self._json({"error": "未检测到有效链接"}, 400)
            return
        if len(urls) > MAX_URLS_PER_JOB:
            self._json({"error": f"单批最多提交 {MAX_URLS_PER_JOB} 条链接"}, 413)
            return
        output_dir = body.get("output_dir") or DEFAULT_OUTPUT_DIR
        if not isinstance(output_dir, str) or not output_dir.strip():
            self._json({"error": "保存位置格式无效"}, 400)
            return
        mode = body.get("mode", "auto")
        if mode not in DELAY_MODES:
            self._json({"error": "下载节奏无效", "supported_modes": sorted(DELAY_MODES)}, 400)
            return
        adaptive = mode == "auto"
        delay = DELAY_MODES[mode]
        image_format = body.get("image_format", "keep")
        if image_format not in {"jpg", "png", "keep"}:
            self._json({"error": "图片格式无效"}, 400)
            return

        idempotency_key = self.headers.get("Idempotency-Key", "").strip()
        if len(idempotency_key) > 128:
            self._json({"error": "Idempotency-Key 最长 128 个字符"}, 400)
            return
        fingerprint = hashlib.sha256(
            json.dumps(
                {"urls": urls, "output_dir": output_dir, "mode": mode, "image_format": image_format},
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        job_id = uuid.uuid4().hex
        duplicate = None
        conflict = False
        with JOBS_LOCK:
            now = time.time()
            for key in [key for key, value in JOB_IDEMPOTENCY.items() if value["expires_at"] <= now]:
                JOB_IDEMPOTENCY.pop(key, None)
            cached = JOB_IDEMPOTENCY.get(idempotency_key) if idempotency_key else None
            if cached and cached["fingerprint"] != fingerprint:
                conflict = True
            elif cached:
                duplicate = copy.deepcopy(JOBS.get(cached["job_id"]))
                if duplicate is None:
                    with WEB_HISTORY_LOCK:
                        duplicate = copy.deepcopy(next((value for value in WEB_HISTORY if value.get("job_id") == cached["job_id"]), None))
                    if duplicate is None:
                        JOB_IDEMPOTENCY.pop(idempotency_key, None)
            if not conflict and duplicate is None:
                if len(JOBS) >= 50:
                    oldest = min(JOBS, key=lambda key: JOBS[key]["created_at"])
                    JOBS.pop(oldest, None)
                JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "queued",
                    "created_at": now,
                    "total": len(urls),
                    "done": 0,
                    "success": 0,
                    "failed": 0,
                    "items": [],
                    "error": "",
                    "output_dir": output_dir,
                    "mode": mode,
                    "image_format": image_format,
                }
                if idempotency_key:
                    JOB_IDEMPOTENCY[idempotency_key] = {
                        "fingerprint": fingerprint,
                        "job_id": job_id,
                        "expires_at": now + 24 * 60 * 60,
                    }
                    while len(JOB_IDEMPOTENCY) > 2000:
                        JOB_IDEMPOTENCY.pop(next(iter(JOB_IDEMPOTENCY)))
        if conflict:
            self._json({"error": "Idempotency-Key 已用于不同的请求内容"}, 409)
            return
        if duplicate is not None:
            status_code = 200 if duplicate.get("status") in {"completed", "error"} else 202
            self._json(
                {"job_id": duplicate.get("job_id", ""), "status": duplicate.get("status", "queued"), "total": duplicate.get("total", len(urls)), "deduplicated": True},
                status_code,
                {"Location": f"/api/v1/jobs/{duplicate.get('job_id', '')}", "Retry-After": "2"},
            )
            return
        worker = threading.Thread(
            target=_run_job,
            args=(job_id, urls, output_dir, delay, image_format, adaptive),
            daemon=True,
        )
        worker.start()
        self._json(
            {"job_id": job_id, "status": "queued", "total": len(urls)},
            202,
            {"Location": f"/api/v1/jobs/{job_id}", "Retry-After": "2"},
        )

    def _html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200, headers=None):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        parsed_origin = urlsplit(origin)
        if parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        if not self._api_path().startswith("/api/"):
            self._json({"error": "not found"}, 404)
            return
        origin = self.headers.get("Origin", "")
        parsed_origin = urlsplit(origin)
        self.send_response(204)
        if parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    host = "127.0.0.1"
    port = 5678
    server = HTTPServer((host, port), Handler)
    url = "http://{}:{}".format(host, port)
    print("{} V{} Web: {}".format(APP_NAME, __version__, url))
    print("Press Ctrl+C to stop")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
