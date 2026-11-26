import subprocess, tempfile, os, time, sys, json, urllib.request, urllib.error, pathlib, csv, io
from openpyxl import Workbook
from playwright.sync_api import sync_playwright
from collector import parse_xml
root=pathlib.Path(__file__).parent
with tempfile.TemporaryDirectory() as td:
 env={**os.environ,'IB_DB':str(pathlib.Path(td)/'test.sqlite3'),'IB_ADMIN_TOKEN':'test-token','PORT':'8765','IB_HOST':'127.0.0.1'}
 server=subprocess.Popen([sys.executable,'server.py'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd=root)
 base='http://127.0.0.1:8765'
 def get(path):
  with urllib.request.urlopen(base+path,timeout=10) as r:return json.load(r)
 def post(path,body,ext,token='test-token'):
  req=urllib.request.Request(base+path,data=body,headers={'Authorization':'Bearer '+token,'X-File-Type':ext})
  with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
 try:
  for i in range(60):
   try:meta=get('/api/meta');break
   except Exception:time.sleep(.2)
  assert sum(x['n'] for x in meta['sources'])==130560
  a=get('/api/analysis');assert len(a['items'])==32 and all(x['score'] is not None for x in a['items']);d=get('/api/detail?hs=3304');assert len(d['trend'])==240 and len(d['countries'])==17
  print('PASS SQL 130,560 demo rows / 32 HS / 120 months / 15 comparison countries + focus + world')
  # Parser fixture only, not live data.
  xml='<response><header><resultCode>00</resultCode></header><body><items><item><year>2025.01</year><statCd>ID</statCd><hsCd>3304</hsCd><statKor>test</statKor><expDlr>12</expDlr><impDlr>20</impDlr><impWgt>2</impWgt></item></items></body></response>'
  assert len(parse_xml(xml,'3304','ID','HS2022'))==2
  r=dict(reporter='ID',partner='KR',flow='M',period='202501',hs='3304',revision='TEST',name='fixture',usd=100,kg=1)
  try:post('/api/import',json.dumps([r]).encode(),'.json','bad');raise AssertionError('auth')
  except urllib.error.HTTPError as e:assert e.code==403
  assert post('/api/import',json.dumps([r]).encode(),'.json')['count']==1
  r['period']='202502';s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(r));w.writeheader();w.writerow(r);assert post('/api/import',s.getvalue().encode(),'.csv')['count']==1
  r['period']='202503';wb=Workbook();ws=wb.active;ws.append(list(r));ws.append(list(r.values()));b=io.BytesIO();wb.save(b);assert post('/api/import',b.getvalue(),'.xlsx')['count']==1
  assert get('/api/analysis?source=imported&revision=TEST')['items']==[] # incomplete year must not be 0
  assert post('/api/catalog-import',b'hs,revision,name\n0101,HS2022,fixture catalog\n','.csv')['count']==1
  assert get('/api/catalog?q=0101')[0]['hs']=='0101'
  print('PASS JSON / CSV / XLSX / HS catalog / auth / incomplete month guard / KCS XML fixture')
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());
   def bridge_fetch(path):
    with urllib.request.urlopen(base+path,timeout=10) as resp:return {'ok':True,'data':json.load(resp)}
   page.expose_function('bridgeFetch',bridge_fetch)
   page.evaluate("() => {Object.defineProperty(window,'localStorage',{value:{_m:{},getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=v}}});window.fetch=async function(path){let r=await window.bridgeFetch(path);return {ok:r.ok,json:async()=>r.data}}}")
   html=(root/'web/index.html').read_text().replace('<link rel="stylesheet" href="/style.css">','<style>'+(root/'web/style.css').read_text()+'</style>').replace('<script src="/app.js"></script>','<script>'+(root/'web/app.js').read_text()+'</script>')
   page.set_content(html);page.wait_for_selector('.kpi');page.screenshot(path=str(root.parent/'Indonesia_Bridge_v02_preview.png'),full_page=True)
   page.get_by_role('button',name='글로벌 무역 탐색').click();page.wait_for_selector('tbody tr');page.locator('#query').fill('3304');page.wait_for_timeout(600);assert page.locator('tbody tr').count()==1;page.locator('tbody a').click();page.wait_for_selector('#trend');page.get_by_role('button',name='월간',exact=True).click();assert page.locator('#trend circle').count()==240;page.get_by_role('button',name='관심 목록 추가').click();page.get_by_role('button',name='관심 품목',exact=True).click();assert page.locator('tbody tr').count()==1
   page.get_by_role('button',name='수출입 마진 계산').click();assert 'Rp 168,475' in page.locator('#profitResult').inner_text();page.locator('#sell').fill('300000');assert 'Rp 101,525' in page.locator('#profitResult').inner_text();page.get_by_role('button',name='데이터 운영').click();assert '가상 부하 데이터' in page.locator('#view').inner_text();assert not errors,errors;legacy=browser.new_page();legacy.evaluate("() => {Object.defineProperty(window,'localStorage',{value:{_m:{},getItem(k){return this._m[k]??null},setItem(k,v){this._m[k]=v}}})}");legacy.set_content((root/'legacy/index.html').read_text());legacy.wait_for_selector('#nav button');assert legacy.locator('#nav button').count()==8;browser.close()
  print('PASS browser search, detail, monthly chart, watch, calculator, ops, legacy 8 menus; no uncaught JS errors')
 finally:server.terminate();server.wait(timeout=5)
