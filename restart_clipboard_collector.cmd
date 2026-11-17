@echo off
title 万能素材剪贴板采集 - 一键秒级重启与看门狗激活
chcp 65001 >nul
cd /d "%~dp0"
echo =======================================================
echo   🔄 正在执行剪贴板采集器与看门狗一键秒级重启...
echo =======================================================
"C:\Users\z\AppData\Local\Programs\Python\Python311\python.exe" -c "
import os, sys, time, subprocess, psutil, json
from pathlib import Path

print('1. 正在清理旧采集器、旧看门狗并拔除残留暂停锁...')
pause_file = Path(r'D:\AICode\运行数据\应用状态\后台服务控制\clipboard-collector.paused')
if pause_file.exists():
    try:
        pause_file.unlink()
        print('   ✔ 已拔除安全暂停锁')
    except Exception as e:
        print(f'   ⚠️ 拔除暂停锁提示: {e}')

for p in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'universal_clipboard_collector' in cmd or 'universal_clipboard_watchdog' in cmd:
            p.kill()
            print(f'   ✔ 已停止进程 PID={p.pid}')
    except Exception:
        pass

time.sleep(1.0)
print('2. 正在以脱壳无窗口模式拉起看门狗 (Watchdog)...')
pythonw = r'C:\Users\z\AppData\Local\Programs\Python\Python311\pythonw.exe'
work_dir = r'D:\AICode\工具开发\projects\xhs-dl'
wd_script = os.path.join(work_dir, 'universal_clipboard_watchdog.py')
env = os.environ.copy()
env['MATERIAL_HUB_CONFIG'] = r'D:\AICode\AI\skills\技能包\技能\universal-clipboard-collector\config\config.json'
subprocess.Popen([pythonw, wd_script], cwd=work_dir, env=env, creationflags=0x08000000, close_fds=True)

print('3. 正在等待采集器自愈并校验心跳...', end='', flush=True)
hb_file = Path(r'D:\AICode\工具开发\projects\xhs-dl\collector_heartbeat.json')
for _ in range(20):
    time.sleep(0.5)
    print('.', end='', flush=True)
    if hb_file.exists():
        try:
            hb = json.loads(hb_file.read_text(encoding='utf-8'))
            age = time.time() - float(hb.get('timestamp', 0))
            if age <= 10:
                print('\n')
                print('=======================================================')
                print('  🎉 剪贴板采集器已成功拉起，看门狗保活已常驻！')
                print(f'  ● 守护进程 PID: {hb.get(\"pid\")}')
                print(f'  ● 采集路由模式: 🤖 全自动智能识别分类')
                print(f'  ● 心跳健康度:   🟢 极速响应 ({int(age)} 秒内新鲜活跃)')
                print(f'  ● 已入库作品:   {hb.get(\"history_len\", 0)} 套 ｜ 排队: {hb.get(\"queue_len\", 0)}')
                print('  ● 看门狗机制:   异常退出 3 秒内全自动原地复活')
                print('=======================================================')
                sys.exit(0)
        except Exception:
            pass

print('\n⚠️ 启动验证耗时较长，请运行 doctor.py 查看详细日志。')
"
echo.
pause
