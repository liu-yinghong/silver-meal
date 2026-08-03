# -*- coding: utf-8 -*-
"""为 50 个餐品批量生成高清食物实拍图（通义万相 wanx2.1-t2i-turbo，异步任务）。
结果保存到 frontend/elder/images/meal_XXX_ui.png（覆盖原插画，image_url 不变）。
"""
import os, sys, json, time, urllib.request, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEALS_FILE = os.path.join(BASE, 'data', 'meals.json')
IMG_DIR = os.path.join(BASE, 'frontend', 'elder', 'images')
LOG = os.path.join(BASE, 'tmp', 'gen_images.log')
KEY = os.environ.get('OPENAI_API_KEY', '')
SUBMIT_URL = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis'
TASK_URL = 'https://dashscope.aliyuncs.com/api/v1/tasks/'
SIZE = '1280*720'
MAX_ATTEMPT = 3

def log(msg):
    line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def api_headers():
    return {'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'}

def submit(prompt):
    body = {'model': 'wanx2.1-t2i-turbo', 'input': {'prompt': prompt},
            'parameters': {'size': SIZE, 'n': 1}}
    req = urllib.request.Request(SUBMIT_URL, data=json.dumps(body).encode('utf-8'),
                                 headers={**api_headers(), 'X-DashScope-Async': 'enable'}, method='POST')
    d = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))
    return (d.get('output') or {}).get('task_id')

def query(tid):
    req = urllib.request.Request(TASK_URL + tid, headers=api_headers(), method='GET')
    d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))
    out = d.get('output', {})
    return out.get('task_status'), out.get('results')

def download(url, path):
    tmp = path + '.tmp'
    urllib.request.urlretrieve(url, tmp)
    os.replace(tmp, path)

def build_prompt(meal):
    name = meal.get('name', '')
    desc = meal.get('description', '')
    return ('高清美食实拍照片，%s，%s，整套菜品配餐具摆盘，菜品配置清晰可见，'
            '白色浅色餐具，饭店出品，柔和自然光，美食摄影，细节清晰锐利，画面干净专业' % (name, desc))

def main():
    meals = json.load(open(MEALS_FILE, encoding='utf-8'))
    if isinstance(meals, dict):
        meals = meals.get('meals', [])
    jobs = {}   # meal_id -> {'task_id':..., 'attempt':..., 'prompt':...}
    pending = []  # list of meal_id currently waiting for result

    # ---- 提交所有任务 ----
    for m in meals:
        mid = m['id']
        prompt = build_prompt(m)
        tid = None
        for attempt in range(1, MAX_ATTEMPT + 1):
            try:
                tid = submit(prompt)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(10)
                    continue
                log('提交失败 %s (HTTP %s): %s' % (mid, e.code, e.read().decode('utf-8')[:200]))
                time.sleep(2)
                continue
            except Exception as e:
                log('提交异常 %s: %s' % (mid, e))
                time.sleep(2)
        if tid:
            jobs[mid] = {'task_id': tid, 'attempt': 1, 'prompt': prompt}
            pending.append(mid)
            log('已提交 %s -> %s' % (mid, tid))
        else:
            log('跳过 %s（提交失败）' % mid)
        time.sleep(0.4)

    # ---- 轮询所有任务直至完成 ----
    done, failed = 0, 0
    total = len(pending)
    while pending:
        idx = 0
        while idx < len(pending):
            mid = pending[idx]
            job = jobs[mid]
            try:
                status, results = query(job['task_id'])
            except Exception as e:
                log('查询异常 %s: %s' % (mid, e))
                idx += 1
                continue
            if status == 'SUCCEEDED' and results and results[0].get('url'):
                url = results[0]['url']
                path = os.path.join(IMG_DIR, mid + '_ui.png')
                try:
                    download(url, path)
                    done += 1
                    log('完成 %s (%d/%d) -> %s' % (mid, done, total, os.path.basename(path)))
                    pending.pop(idx)
                    continue
                except Exception as e:
                    log('下载失败 %s: %s' % (mid, e))
                    idx += 1
                    continue
            elif status == 'FAILED' or (results and not results[0].get('url')):
                job['attempt'] += 1
                if job['attempt'] <= MAX_ATTEMPT:
                    try:
                        new_tid = submit(job['prompt'])
                        job['task_id'] = new_tid
                        log('重试 %s (%d/%d) -> %s' % (mid, job['attempt'] - 1, MAX_ATTEMPT, new_tid))
                    except Exception as e:
                        log('重试提交失败 %s: %s' % (mid, e))
                else:
                    failed += 1
                    log('失败 %s（已重试 %d 次）' % (mid, MAX_ATTEMPT))
                    pending.pop(idx)
                    continue
            idx += 1
        time.sleep(3)

    log('全部完成：成功 %d，失败 %d，共 %d' % (done, failed, total))

if __name__ == '__main__':
    main()
