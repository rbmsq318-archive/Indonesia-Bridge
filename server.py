from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from pathlib import Path
import json, os, csv, io, hmac, tempfile, re
from data import ROOT, connect, init,seed,ingest,parse_file,catalog,COUNTRIES,PARTNERS

def rows(c,sql,params=()):return [dict(r) for r in c.execute(sql,params)]
def scope(q):
 s=q.get('source','demo');reporter=q.get('reporter','ID');flow=q.get('flow','M');rev=q.get('revision','demo');year=int(q.get('year','2025'));level=int(q.get('level','4'))
 if s not in ('demo','kcs','imported') or reporter not in ('ID','KR') or flow not in ('M','X') or level not in (2,4,6,10) or not 2000<=year<=2099:raise ValueError('invalid filters')
 return [s,reporter,flow,rev,level],year
BASE='source=? AND reporter=? AND flow=? AND revision=? AND length(hs)=?'
def analysis(q):
 args,y=scope(q);focus='KR' if args[1]=='ID' else 'ID';query=q.get('q','').strip();
 with connect() as c:
  # A year is comparable only for complete 12-month observations; world must be explicit, not competitor sum.
  rs=rows(c,f'''WITH a AS (SELECT hs,MAX(name) name,partner,substr(period,1,4) yr,SUM(usd) usd,COUNT(DISTINCT period) n FROM trade WHERE {BASE} AND period BETWEEN ? AND ? AND partner IN (?, 'WORLD') GROUP BY hs,partner,yr) SELECT hs,MAX(name) name,MAX(CASE WHEN partner='WORLD' AND yr=? AND n=12 THEN usd END) world,MAX(CASE WHEN partner='WORLD' AND yr=? AND n=12 THEN usd END) prev,MAX(CASE WHEN partner=? AND yr=? AND n=12 THEN usd END) bilateral,MAX(CASE WHEN partner=? AND yr=? AND n=12 THEN usd END) bilateral_prev FROM a GROUP BY hs''',(*args,f'{y-1}01',f'{y}12',focus,str(y),str(y-1),focus,str(y),focus,str(y-1)))
  for r in rs:
   w,p,b,bp=[r[k] for k in ('world','prev','bilateral','bilateral_prev')];r['growth']=(w/p-1)*100 if w is not None and p and p>0 else None;r['share']=b/w*100 if b is not None and w and b<=w else None;r['bilateral_growth']=(b/bp-1)*100 if b is not None and bp and bp>0 else None
   r['score']=round(max(0,min(1,(r['growth'] or 0)/25))*45+min(1,__import__('math').log10(max(w,1))/10)*35+(1-r['share']/100)*20,1) if r['growth'] is not None and r['share'] is not None else None
  rs=[r for r in rs if (r['world'] is not None or r['bilateral'] is not None) and (not query or query.lower() in (r['hs']+' '+r['name']).lower())];rs.sort(key=lambda r:r['bilateral'] or 0,reverse=True)
  counts=c.execute('SELECT count(*) FROM trade WHERE '+BASE,args).fetchone()[0]
  return {'items':rs,'count':counts,'focus':focus,'year':y}
def detail(q):
 args,y=scope(q);hs=q.get('hs','');focus='KR' if args[1]=='ID' else 'ID'
 if not re.fullmatch(r'\d{2}|\d{4}|\d{6}|\d{10}',hs):raise ValueError('invalid HS')
 with connect() as c:
  trend=rows(c,f'''SELECT period,partner,usd,kg FROM trade WHERE {BASE} AND hs=? AND partner IN (?, 'WORLD') ORDER BY period''',(*args,hs,focus));countries=rows(c,f'''SELECT partner,SUM(usd) usd,COUNT(DISTINCT period) months FROM trade WHERE {BASE} AND hs=? AND period BETWEEN ? AND ? GROUP BY partner ORDER BY usd DESC''',(*args,hs,f'{y}01',f'{y}12'));return {'trend':trend,'countries':countries,'focus':focus,'hs':hs}
class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args): print(fmt%args,flush=True)
 def send(self,obj,status=200,typ='application/json; charset=utf-8'):
  body=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type',typ);self.send_header('Content-Length',len(body));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  u=urlparse(self.path);q={k:v[0] for k,v in parse_qs(u.query).items()};p=u.path
  try:
   if p in ('/','/app.js','/style.css','/legacy'):
    file,typ={'/':('web/index.html','text/html'),'/app.js':('web/app.js','text/javascript'),'/style.css':('web/style.css','text/css'),'/legacy':('legacy/index.html','text/html')}[p];return self.send((ROOT/file).read_bytes(),typ=typ+'; charset=utf-8')
   if p=='/api/meta':
    with connect() as c:return self.send({'sources':rows(c,'SELECT source,revision,reporter,flow,length(hs) level,count(*) n, min(period) start,max(period) end FROM trade GROUP BY 1,2,3,4,5'),'countries':COUNTRIES,'partners':PARTNERS,'catalog':c.execute('SELECT count(*) FROM hs_catalog').fetchone()[0],'runs':rows(c,'SELECT * FROM runs ORDER BY ts DESC LIMIT 10')})
   if p=='/api/analysis':return self.send(analysis(q))
   if p=='/api/detail':return self.send(detail(q))
   if p=='/api/catalog':
    t='%'+q.get('q','')+'%'
    with connect() as c:return self.send(rows(c,'SELECT hs,revision,name FROM hs_catalog WHERE hs LIKE ? OR name LIKE ? UNION SELECT DISTINCT hs,revision,name FROM trade WHERE source=? AND (hs LIKE ? OR name LIKE ?) ORDER BY hs LIMIT 100',(t,t,q.get('source','demo'),t,t)))
   if p=='/api/raw':
    a,y=scope(q);hs=q.get('hs','');cond=BASE+' AND period BETWEEN ? AND ?';params=[*a,f'{y}01',f'{y}12'];
    if hs:cond+=' AND hs=?';params.append(hs)
    with connect() as c:
     cur=c.execute('SELECT * FROM trade WHERE '+cond+' ORDER BY hs,period,partner',params);out=io.StringIO();w=csv.writer(out);w.writerow([d[0] for d in cur.description]);
     for row in cur:w.writerow([("'"+x if isinstance(x,str) and x.startswith(('=','+','-','@','\t','\r')) else x) for x in row])
    return self.send(('\ufeff'+out.getvalue()).encode(),typ='text/csv; charset=utf-8')
   self.send({'error':'not found'},404)
  except (ValueError,TypeError,KeyError) as e:self.send({'error':str(e)},400)
  except Exception as e:print(type(e).__name__,flush=True);self.send({'error':'server error'},500)
 def do_POST(self):
  if self.path not in ('/api/import','/api/catalog-import'):return self.send({'error':'not found'},404)
  key=os.getenv('IB_ADMIN_TOKEN','')
  if not key or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+key):return self.send({'error':'admin token required; configure IB_ADMIN_TOKEN or use CLI'},403)
  try:
   n=int(self.headers.get('Content-Length','0'));ext=self.headers.get('X-File-Type','')
   if not 0<n<=50_000_000 or ext not in ('.csv','.json','.xlsx'):raise ValueError('invalid file or size; max 50 MB')
   with tempfile.NamedTemporaryFile(suffix=ext,delete=False) as f:f.write(self.rfile.read(n));path=f.name
   try:items=parse_file(path);count=catalog(items) if self.path.endswith('catalog-import') else ingest(items,'imported')
   finally:Path(path).unlink(missing_ok=True)
   self.send({'count':count})
  except Exception as e:self.send({'error':str(e)[:200]},400)
if __name__=='__main__':
 init();seed();host=os.getenv('IB_HOST','127.0.0.1');port=int(os.getenv('PORT','8000'));print(f'Indonesia Bridge listening {host}:{port}',flush=True);ThreadingHTTPServer((host,port),Handler).serve_forever()
