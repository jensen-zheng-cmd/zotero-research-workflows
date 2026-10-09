"""Store validated PDFs under existing Zotero parents via the Zotero 10 local API."""
import argparse, hashlib, json, pathlib, re, urllib.request, urllib.parse, urllib.error, uuid
import pymupdf
import runtime_config as runtime

def words(text):
    return set(re.sub(r'[^a-z0-9 ]',' ',text.lower().replace('centres','centers')).split())

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--input',required=True); parser.add_argument('--collection',required=True)
    parser.add_argument('--out',required=True); parser.add_argument('--data-dir',default=runtime.data_dir_default())
    parser.add_argument('--run',action='store_true',help='Write attachments; otherwise validate and plan only')
    args=parser.parse_args(); args.data_dir=runtime.require_data_dir(args.data_dir)
    rows=json.loads(pathlib.Path(args.input).read_text(encoding='utf-8'))
    root=pathlib.Path(args.out); root.mkdir(parents=True,exist_ok=True); base=runtime.settings()['api_base']
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); key=None; remembered=False
    with opener.open(base+'/api/',timeout=10) as response: server=response.headers['Zotero-Server-ID']
    def request(path,data=None,headers=None,timeout=60):
        req=urllib.request.Request(base+path,data=data,headers={'Zotero-Server-ID':server,'Zotero-Allowed-Request':'1',**(headers or {})})
        with opener.open(req,timeout=timeout) as response:
            body=response.read(); return (json.loads(body) if body else None,response.status)
    def authorize():
        nonlocal key,remembered
        if not key:
            print(json.dumps({'action_required':'local_authorization','app_name':'Codex Zotero Local Batch'},ensure_ascii=False),flush=True)
            auth,_=request('/api/local/authorize',json.dumps({'appName':'Codex Zotero Local Batch'}).encode(),{'Content-Type':'application/json'},600)
            key=auth['key']; remembered=bool(auth.get('remember'))
    def write(path,data,headers=None):
        nonlocal key
        authorize()
        result=request(path,data,{'Zotero-API-Key':key,**(headers or {})})
        if not remembered: key=None
        return result
    manifest=[]
    for row in rows:
        if row.get('status')!='downloaded': continue
        source=pathlib.Path(row['path']).resolve(); payload=source.read_bytes()
        if not payload.startswith(b'%PDF-'): raise ValueError('Not PDF: '+str(source))
        with pymupdf.open(source) as doc:
            if doc.needs_pass or not doc.page_count: raise ValueError('Unreadable PDF')
            text=' '.join(doc[i].get_text() for i in range(min(3,doc.page_count))); pages=doc.page_count
        expected=words(row.get('pdf_title',row['title'])); overlap=len(expected & words(text))/max(len(expected),1)
        if overlap<.8: raise ValueError('Review PDF title: '+row['title'])
        parent,_=request('/api/users/0/items/'+row['parent_key']); parent=parent['data']
        if args.collection not in parent.get('collections',[]) or words(parent['title'])!=words(row['title']): raise ValueError('Parent identity or collection changed')
        children,_=request('/api/users/0/items/'+row['parent_key']+'/children')
        sha=hashlib.sha256(payload).hexdigest(); existing=None
        for child in children:
            d=child['data']
            if d.get('contentType')!='application/pdf' or d.get('linkMode') not in ('imported_file','imported_url'): continue
            stored=pathlib.Path(args.data_dir,'storage',child['key'],d.get('filename',''))
            if stored.is_file() and hashlib.sha256(stored.read_bytes()).hexdigest()==sha: existing=child['key']; break
        manifest.append({**{k:v for k,v in row.items() if k!='first_pages_text'},'pages':pages,'sha256':sha,'identity_overlap':overlap,'existing_attachment_key':existing})
    plan_file=root/'plan.json'
    if not plan_file.exists(): plan_file.write_text(json.dumps({'server_id':server,'collection':args.collection,'files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        old=json.loads(plan_file.read_text(encoding='utf-8'))
        if old['server_id']!=server: raise ValueError('Database changed')
        if old['collection']!=args.collection or [(r['parent_key'],r['sha256']) for r in old['files']]!=[(r['parent_key'],r['sha256']) for r in manifest]:
            raise ValueError('Plan input changed; use a new output folder')
    if not args.run:
        print(json.dumps({'mode':'plan_only','validated':len(manifest),'already_attached':sum(bool(r['existing_attachment_key']) for r in manifest)},ensure_ascii=False),flush=True)
        return
    report_file=root/'report.json'; results=json.loads(report_file.read_text(encoding='utf-8')).get('results',[]) if report_file.exists() else []
    def save(): report_file.write_text(json.dumps({'server_id':server,'collection':args.collection,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    for row in manifest:
        if row['existing_attachment_key']:
            if not any(r['parent_key']==row['parent_key'] and r.get('sha256')==row['sha256'] for r in results):
                results.append({'parent_key':row['parent_key'],'attachment_key':row['existing_attachment_key'],'status':'already_attached','sha256':row['sha256']}); save()
            continue
        progress=[r for r in results if r['parent_key']==row['parent_key'] and r.get('sha256')==row['sha256']]
        if progress:
            result=progress[-1]
            if 'attachment_key' not in result: raise RuntimeError('Unconfirmed attachment creation; inspect library before retry')
            attachment=result['attachment_key']
        else:
            authorize()
            result={'parent_key':row['parent_key'],'title':row['title'],'sha256':row['sha256'],'status':'creating','edition':row.get('edition','author_version')}
            results.append(result); save()
            item={'itemType':'attachment','parentItem':row['parent_key'],'linkMode':'imported_file','title':'PDF ('+result['edition']+')','contentType':'application/pdf','filename':pathlib.Path(row['path']).name,'url':row.get('source_url','')}
            response,_=write('/api/users/0/items',json.dumps([item]).encode(),{'Content-Type':'application/json','Zotero-Write-Token':uuid.uuid4().hex})
            if response.get('failed'): raise RuntimeError('Create failed: '+str(response['failed']))
            attachment=response['successful']['0']['key']; result.update(attachment_key=attachment,status='created'); save()
        file=pathlib.Path(row['path']); payload=file.read_bytes(); md5=hashlib.md5(payload).hexdigest()
        params=urllib.parse.urlencode({'md5':md5,'filename':file.name,'filesize':len(payload),'mtime':int(file.stat().st_mtime*1000)}).encode()
        endpoint='/api/users/0/items/'+attachment+'/file'; headers={'Content-Type':'application/x-www-form-urlencoded','If-None-Match':'*'}
        info,_=write(endpoint,params,headers)
        if not info.get('exists'):
            url=urllib.parse.urlsplit(info['url']); origin=urllib.parse.urlsplit(base)
            if url.scheme and (url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost','::1') or url.port!=origin.port): raise ValueError('Upload URL is not local Zotero')
            request(url.path,payload,{'Content-Type':info['contentType']},90)
            write(endpoint,urllib.parse.urlencode({'upload':info['uploadKey']}).encode(),headers)
        child,_=request('/api/users/0/items/'+attachment); d=child['data']
        stored=pathlib.Path(args.data_dir,'storage',attachment,d['filename'])
        if not stored.is_file() or hashlib.sha256(stored.read_bytes()).hexdigest()!=row['sha256']: raise RuntimeError('Stored file hash mismatch')
        with pymupdf.open(stored) as doc:
            if not doc.is_pdf or doc.needs_pass or doc.page_count!=row['pages']: raise RuntimeError('Stored PDF unreadable')
        result.update(status='verified',stored_path=str(stored),pages=row['pages'],identity_overlap=row['identity_overlap']); save()
        print(json.dumps({'parent_key':row['parent_key'],'attachment_key':attachment,'status':'verified'},ensure_ascii=False),flush=True)
    verified=len([r for r in results if r['status'] in ('verified','already_attached')])
    summary={'requested':len(rows),'downloaded':len(manifest),'verified':verified,'missing':len(rows)-verified,
             'unavailable':[r.get('title') for r in rows if r.get('status')!='downloaded']}
    (root/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return 0 if verified==len(rows) else 2

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'error':str(exc),'action_required':'inspect_report_and_local_state'},ensure_ascii=False),flush=True)
        raise SystemExit(1)
