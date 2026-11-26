#!/usr/bin/env python3
"""Local-only data pipeline. No scraping, mail delivery, payment or external API calls."""
import argparse, csv, datetime as dt, json, math, pathlib, re, sys

def validate(doc):
    if not isinstance(doc,dict) or not isinstance(doc.get('dataset_name'),str) or not doc['dataset_name'].strip() or not isinstance(doc.get('rows'),list) or not 0<len(doc['rows'])<=100000: raise ValueError('Invalid dataset name or row count')
    seen=set(); names={}
    for r in doc['rows']:
        if not isinstance(r,dict) or r.get('direction') not in ('KR_ID','ID_KR') or not isinstance(r.get('hs'),str) or not re.fullmatch(r'\d{4}',r['hs']) or any(not isinstance(r.get(k),str) or not r[k].strip() for k in ('name','sector')) or type(r.get('year')) is not int or not 1900<=r['year']<=2100: raise ValueError(f'Invalid record: {r}')
        for k in ('market_usd','bilateral_usd'):
            if type(r.get(k)) not in (int,float) or not math.isfinite(r[k]) or r[k]<0: raise ValueError(f'Invalid number: {r}')
        if r['bilateral_usd']>r['market_usd']: raise ValueError('Bilateral exceeds market')
        k=(r['direction'],r['hs'],r['year']); n=k[:2]; v=(r['name'],r['sector'])
        if k in seen or (n in names and names[n]!=v): raise ValueError(f'Duplicate or inconsistent metadata: {k}')
        seen.add(k); names[n]=v
    return doc

def calculate(rows,direction):
    rows=[r for r in rows if r['direction']==direction]
    if not rows:return []
    latest=max(r['year'] for r in rows); lookup={(r['hs'],r['year']):r for r in rows}; current=[r for r in rows if r['year']==latest]; maximum=max(1,max(r['market_usd'] for r in current)); result=[]
    for r in current:
        prev=lookup.get((r['hs'],latest-1)); g=(r['market_usd']/prev['market_usd']-1)*100 if prev and prev['market_usd']>0 else None; s=r['bilateral_usd']/r['market_usd']*100 if r['market_usd']>0 else None
        score=math.floor(45*max(0,min(1,g/25))+35*math.log1p(r['market_usd'])/math.log1p(maximum)+20*(1-s/100)+.5) if g is not None and s is not None else None
        result.append(dict(r,growth_pct=g,share_pct=s,score=score))
    return sorted(result,key=lambda r:(-(r['score'] if r['score'] is not None else -1),-r['market_usd']))

def run(dataset,watch_file,out):
    doc=validate(json.loads(dataset.read_text(encoding='utf-8-sig'))); rows=doc['rows']; mode='demo' if doc.get('mode')=='demo' else 'imported_unverified'; now=dt.datetime.now(dt.timezone.utc).isoformat(); out.mkdir(parents=True,exist_ok=True)
    watch=json.loads(watch_file.read_text(encoding='utf-8-sig')) if watch_file else []
    if not isinstance(watch,list) or any(not isinstance(w,dict) or w.get('direction') not in ('KR_ID','ID_KR') or not isinstance(w.get('hs'),str) for w in watch):raise ValueError('Invalid watchlist')
    ranked=sum((calculate(rows,d) for d in ('KR_ID','ID_KR')),[]); lookup={(r['direction'],r['hs']):r for r in ranked}; alerts=[]
    for w in watch:
        r=lookup.get((w['direction'],w['hs'])); alerts.append({'direction':w['direction'],'hs':w['hs'],'mode':mode,'generated_at':now,'result':r,'status':'draft_not_sent'})
    fields=['dataset_mode','direction','year','hs','name','sector','market_usd','bilateral_usd','growth_pct','share_pct','score']
    def safe(v):return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v
    with (out/'ranked.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({k:safe(v) for k,v in dict(r,dataset_mode=mode).items() if k in fields} for r in ranked)
    (out/'alert_drafts.json').write_text(json.dumps(alerts,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[f'Indoneisa Bridge | {mode}',f'Generated: {now}',f'Dataset: {doc["dataset_name"]}',f'Source: {doc.get("source_url") or "not specified"}','No commercial distribution before rights verification.','Scores are screening indicators, not success probabilities.']
    for d in ('KR_ID','ID_KR'):
        lines += ['',d]+[f'{r["hs"]} {r["name"]}: USD {r["market_usd"]:,}, score {r["score"]}' for r in ranked if r['direction']==d][:5]
    (out/'report.txt').write_text('\n'.join(lines),encoding='utf-8')
    log={'timestamp':now,'mode':mode,'rows':len(rows),'ranked':len(ranked),'alert_drafts':len(alerts),'status':'success_local_only'}
    with (out/'run_log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(log,ensure_ascii=False)+'\n')
    print(json.dumps(log,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=pathlib.Path,default=pathlib.Path(__file__).with_name('sample_data.json'));p.add_argument('--watch',type=pathlib.Path);p.add_argument('--out',type=pathlib.Path,default=pathlib.Path('output'));a=p.parse_args()
    try:run(a.input,a.watch,a.out)
    except Exception as e:print(f'Pipeline failed: {e}',file=sys.stderr);sys.exit(1)
