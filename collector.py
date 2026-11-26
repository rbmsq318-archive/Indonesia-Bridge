"""Korea Customs documented XML adapter. Uses Korean reporter only; never substitutes ID imports."""
import argparse, os, urllib.request, urllib.parse, xml.etree.ElementTree as ET, time, re
from data import ingest
ENDPOINT='https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList'
def parse_xml(body,hs,partner,revision):
 root=ET.fromstring(body); code=root.findtext('.//resultCode')
 if code not in ('00','0'):raise ValueError('KCS response not successful: '+str(code))
 rows=[]
 for item in root.findall('.//item'):
  period=(item.findtext('year') or '').replace('.',''); code=item.findtext('hsCd') or ''
  if not re.fullmatch(r'20\d{2}(0[1-9]|1[0-2])',period) or code!=hs:continue
  if item.findtext('statCd')!=partner:raise ValueError('unexpected country')
  for flow,prefix in [('M','imp'),('X','exp')]:
   amt=item.findtext(prefix+'Dlr');weight=item.findtext(prefix+'Wgt')
   if amt in (None,'','-'):continue
   rows.append(dict(reporter='KR',partner=partner,flow=flow,period=period,hs=code,revision=revision,name=item.findtext('statKor') or code,usd=amt,kg=weight if weight not in ('-',None,'') else None))
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--hs',required=True,help='comma-separated codes');p.add_argument('--partners',default='ID');p.add_argument('--start',type=int,default=2016);p.add_argument('--end',type=int,default=2025);p.add_argument('--revision',required=True,help='confirmed HS version, do not combine revisions');p.add_argument('--max-calls',type=int,default=100);a=p.parse_args();key=os.getenv('KCS_SERVICE_KEY');
 if not key:raise SystemExit('Set KCS_SERVICE_KEY using decoded API key (never in code)')
 if a.start>a.end or a.max_calls<1:raise SystemExit('invalid range')
 calls=0;total=0
 for year in range(a.start,a.end+1):
  for hs in a.hs.split(','):
   for partner in a.partners.split(','):
    if calls>=a.max_calls:raise SystemExit(f'call budget reached; rows stored {total}')
    params=dict(serviceKey=key,strtYymm=f'{year}01',endYymm=f'{year}12',hsSgn=hs,cntyCd=partner)
    try:
     with urllib.request.urlopen(ENDPOINT+'?'+urllib.parse.urlencode(params),timeout=30) as r:rows=parse_xml(r.read(),hs,partner,a.revision)
     if rows:total+=ingest(rows,'kcs')
     calls+=1;print(year,hs,partner,len(rows),flush=True);time.sleep(.3)
    except Exception as e:raise SystemExit(f'collection halted at {year}/{hs}/{partner}: {type(e).__name__}; inspect credentials/quota or response')
 print('stored',total,'calls',calls)
