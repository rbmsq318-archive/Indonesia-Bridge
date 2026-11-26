import sqlite3, os, json, csv, random, re, math, argparse, pathlib, datetime
ROOT=pathlib.Path(__file__).parent
DB=pathlib.Path(os.getenv('IB_DB',str(ROOT/'data'/'bridge.sqlite3')))
COUNTRIES={'KR':'한국','ID':'인도네시아','CN':'중국','JP':'일본','US':'미국','SG':'싱가포르','MY':'말레이시아','TH':'태국','VN':'베트남','AU':'호주','DE':'독일','IN':'인도','TW':'대만','NL':'네덜란드','FR':'프랑스','PH':'필리핀','IT':'이탈리아','WORLD':'세계 전체'}
PARTNERS=['CN','JP','US','SG','MY','TH','VN','AU','DE','IN','TW','NL','FR','PH','IT']
EXTRA={'0202':'냉동 쇠고기','0402':'분유','1006':'쌀','1701':'설탕','1806':'초콜릿','2202':'비알코올 음료','3004':'의약품','3923':'플라스틱 포장용품','4011':'공기타이어','6109':'티셔츠','6403':'가죽 신발','7208':'열간압연 철강','7308':'철강 구조물','8415':'에어컨','8429':'건설기계','8528':'모니터·TV','8703':'승용차','8708':'자동차 부품'}
def connect():
 DB.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB,timeout=30);c.row_factory=sqlite3.Row;return c
def init():
 with connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS trade(source TEXT, reporter TEXT, partner TEXT, flow TEXT, period TEXT, hs TEXT, revision TEXT, name TEXT, usd REAL NOT NULL, kg REAL, PRIMARY KEY(source,reporter,partner,flow,period,hs,revision)); CREATE INDEX IF NOT EXISTS trade_search ON trade(source,reporter,flow,revision,period,hs,partner); CREATE TABLE IF NOT EXISTS hs_catalog(hs TEXT,revision TEXT,name TEXT,PRIMARY KEY(hs,revision)); CREATE TABLE IF NOT EXISTS runs(ts TEXT,source TEXT,status TEXT,detail TEXT);''')

def seed():
 init()
 with connect() as c:
  if c.execute("SELECT 1 FROM trade WHERE source='demo' LIMIT 1").fetchone():return
  legacy=json.loads((ROOT/'legacy/sample_data.json').read_text()); names={r['hs']:r['name'] for r in legacy['rows']};names.update(EXTRA); rng=random.Random(2026); batch=[]
  for hs,name in names.items():
   for reporter,focus in [('ID','KR'),('KR','ID')]:
    ps=[focus]+PARTNERS; weights=[rng.uniform(.5,3) for _ in ps]; denom=sum(weights)*1.15;base=rng.uniform(1e6,50e6);growth=rng.uniform(-.025,.19)
    for year in range(2016,2026):
     for m in range(1,13):
      period=f'{year}{m:02d}'; world=round(base*(1+growth)**(year-2016)*(1+.13*math.sin(m/12*6.28))*rng.uniform(.93,1.07));batch.append(('demo',reporter,'WORLD','M',period,hs,'demo',name,world,None))
      for p,w in zip(ps,weights):batch.append(('demo',reporter,p,'M',period,hs,'demo',name,round(world*w/denom*rng.uniform(.92,1.08)),None))
  c.executemany('INSERT INTO trade VALUES(?,?,?,?,?,?,?,?,?,?)',batch)
  c.execute('INSERT INTO runs VALUES(?,?,?,?)',(datetime.datetime.now(datetime.timezone.utc).isoformat(),'demo','ok',f'{len(batch)} synthetic records'))

def validate(row):
 r={k:str(row.get(k,'')).strip() for k in ['reporter','partner','flow','period','hs','revision','name']};r['reporter']=r['reporter'].upper();r['partner']=r['partner'].upper();r['flow']=r['flow'].upper();r['hs']=r['hs'].split('.')[0];
 if len(r['hs']) in (1,3,5,9):r['hs']=r['hs'].zfill(len(r['hs'])+1)
 if not re.fullmatch(r'\d{2}|\d{4}|\d{6}|\d{10}',r['hs']) or not re.fullmatch(r'20\d{2}(0[1-9]|1[0-2])',r['period']) or r['reporter'] not in ('KR','ID') or not re.fullmatch(r'[A-Z]{2}|WORLD',r['partner']) or r['partner']==r['reporter'] or r['flow'] not in ('M','X') or not r['revision'] or len(r['revision'])>30 or not r['name'] or len(r['name'])>300:raise ValueError('invalid HS/period/reporter/partner/flow/revision/name')
 def num(v,optional=False):
  if optional and (v is None or v==''):return None
  n=float(v)
  if not math.isfinite(n) or n<0:raise ValueError('invalid value')
  return n
 return (*[r[k] for k in ['reporter','partner','flow','period','hs','revision','name']],num(row.get('usd')),num(row.get('kg'),True))
def ingest(rows,source):
 if source not in ('kcs','imported'):raise ValueError('invalid source')
 init(); seen=set(); batch=[]
 for row in rows:
  v=validate(row);key=v[:6]
  if key in seen:raise ValueError(f'duplicate key: {key}')
  seen.add(key);batch.append((source,*v))
 if not batch:raise ValueError('empty data')
 with connect() as c:
  c.executemany('INSERT INTO trade VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,reporter,partner,flow,period,hs,revision) DO UPDATE SET name=excluded.name,usd=excluded.usd,kg=excluded.kg',batch)
  c.execute('INSERT INTO runs VALUES(?,?,?,?)',(datetime.datetime.now(datetime.timezone.utc).isoformat(),source,'ok',f'{len(batch)} rows upserted'))
 return len(batch)
def parse_file(path):
 p=pathlib.Path(path)
 if p.suffix.lower()=='.csv':
  with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 if p.suffix.lower()=='.json':
  x=json.loads(p.read_text(encoding='utf-8-sig'));return x if isinstance(x,list) else x['rows']
 if p.suffix.lower()=='.xlsx':
  from openpyxl import load_workbook
  w=load_workbook(p,read_only=True,data_only=True);it=w.active.values;keys=next(it);rows=[dict(zip(keys,r)) for r in it if any(x is not None for x in r)];w.close();return rows
 raise ValueError('CSV / JSON / XLSX only')
def catalog(rows):
 init();batch=[]
 for r in rows:
  hs=str(r['hs']).strip();rev=str(r['revision']).strip();name=str(r['name']).strip()
  if not re.fullmatch(r'\d{2}|\d{4}|\d{6}|\d{10}',hs) or not rev or not name:raise ValueError('invalid catalog row; preserve HS as text')
  batch.append((hs,rev,name))
 with connect() as c:c.executemany('INSERT OR REPLACE INTO hs_catalog VALUES(?,?,?)',batch)
 return len(batch)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seed','import','catalog']);p.add_argument('file',nargs='?');a=p.parse_args();print(seed() if a.action=='seed' else (catalog(parse_file(a.file)) if a.action=='catalog' else ingest(parse_file(a.file),'imported')))
