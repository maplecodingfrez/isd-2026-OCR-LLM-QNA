"""Prepare, verify and reversibly install the full GE66 image-OCR catalog."""
from contextlib import closing
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import unicodedata

PLANS=('AIT','DSBA/coop','DSBA/no_coop','IT/coop','IT/no_coop')
CATALOG='Lab7B_Lab8B_ocr_system/runs/ge66_catalog.json'
PROVENANCE='Lab7B_Lab8B_ocr_system/runs/ge66_ocr_provenance.json'
FIELDS=('name_th','name_en','credits')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def rows(catalog):
    return [{**r,'group_no':g['group_no']} for g in catalog['groups'] for r in g['courses']]


def verify_catalog(catalog,candidate,observations,summary,*,expected=303):
    selected=rows(catalog);codes=[r['code'] for r in selected]
    p=catalog.get('provenance',{})
    if (len(selected)!=expected or len(set(codes))!=expected or len(candidate)!=expected
        or len({r['code'] for r in candidate})!=expected or '2566' not in catalog['plan_slot']
        or 'image OCR' not in catalog.get('source','') or p.get('method')!='image_only_ocr'
        or p.get('verified_records')!=expected or p.get('raw_ocr_traceable_field_values')!=3*expected
        or p.get('manual_fills')!=0 or p.get('reference_used_as_ocr_prompt_or_field_fill') is not False
        or summary.get('all_fields_exact')!=expected or summary.get('field_values_traceable_to_raw_ocr')!=3*expected
        or summary.get('manually_filled_fields')!=0 or summary.get('page_and_flag_checks') is not True
        or summary.get('reference_used_as_ocr_prompt_or_field_fill') is not False):
        raise ValueError('Full verified GE66 image-only catalog gate failed')
    chosen={r['code']:r for r in candidate}
    for r in selected:
        if not re.fullmatch(r'9064[1-5]\d{3}',r['code']) or r['group_no']!=int(r['code'][4]) or type(r.get('graded_su')) is not bool:
            raise ValueError('Invalid GE66 group/code/SU metadata')
        if r['code'] not in chosen or r['page']!=chosen[r['code']]['page']:
            raise ValueError('Candidate/catalog page mismatch')
        for field in FIELDS:
            if chosen[r['code']].get(field)!=r[field] or not any(o.get(field)==r[field] and o.get('page')==r['page'] for o in observations.get(r['code'],[])):
                raise ValueError('Untraceable raw OCR field: '+r['code']+'/'+field)
        credit(r['credits'])
    return 3*len(selected)


def credit(value):
    match=re.fullmatch(r'(\d+)\s*\((\d+)-(\d+)-(\d+)\)',value)
    if not match:raise ValueError('Incomplete observed credit structure')
    return int(match[1])


def protected_snapshot(conn,slot):
    schema=conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()
    result={'schema':hashlib.sha256(repr(schema).encode()).hexdigest()}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        if name=='elective_group_course':continue
        data=conn.execute('SELECT * FROM "'+name.replace('"','""')+'"').fetchall()
        result[name]=hashlib.sha256(repr(sorted(map(repr,data))).encode()).hexdigest()
    data=conn.execute('SELECT c.* FROM elective_group_course c JOIN elective_group g ON g.id=c.group_id WHERE g.plan_slot<>? ORDER BY c.group_id,c.code',(slot,)).fetchall()
    result['other_elective_courses']=hashlib.sha256(repr(data).encode()).hexdigest()
    return result


def expected_db_rows(catalog):
    return sorted((r['group_no'],r['code'],r['name_th'],r['name_en'],credit(r['credits'])) for r in rows(catalog))


def actual_db_rows(conn,slot):
    return conn.execute('SELECT g.group_no,c.code,c.name_th,c.name_en,c.credits FROM elective_group_course c JOIN elective_group g ON g.id=c.group_id WHERE g.plan_slot=? ORDER BY g.group_no,c.code',(slot,)).fetchall()


def validate_database(path,catalog,untouched):
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite integrity/foreign-key check failed')
        if protected_snapshot(conn,catalog['plan_slot'])!=untouched or actual_db_rows(conn,catalog['plan_slot'])!=expected_db_rows(catalog):
            raise ValueError('GE rows or protected curriculum data/schema changed unexpectedly')


def stage_database(source,destination,catalog):
    if source.resolve()==destination.resolve() or destination.exists():
        raise ValueError('Staging must be a new separate SQLite file')
    with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as original:
        existing=actual_db_rows(original,catalog['plan_slot'])
        if [(r[0],r[1]) for r in existing]!=[(r[0],r[1]) for r in expected_db_rows(catalog)]:
            raise ValueError('Existing full GE66 course/group scope differs; no replacement')
        untouched=protected_snapshot(original,catalog['plan_slot'])
        destination.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(destination)) as copy:original.backup(copy)
    with closing(sqlite3.connect(destination)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            for r in rows(catalog):
                changed=conn.execute('UPDATE elective_group_course SET name_th=?,name_en=?,credits=? WHERE code=? AND group_id IN (SELECT id FROM elective_group WHERE plan_slot=? AND group_no=?)',(r['name_th'],r['name_en'],credit(r['credits']),r['code'],catalog['plan_slot'],r['group_no'])).rowcount
                if changed!=1:raise ValueError('Unexpected target row count')
            if protected_snapshot(conn,catalog['plan_slot'])!=untouched:raise ValueError('Non-GE data changed')
            conn.commit()
        except BaseException:
            conn.rollback();raise
    validate_database(destination,catalog,untouched)
    return untouched


def db_relative(plan):
    return 'Lab7B_Lab8B_ocr_system/runs/'+plan+'/lab8b_output/curriculum.db'


def checked_entries(manifest,expected_state):
    if manifest['state']!=expected_state:raise ValueError('Manifest state differs')
    root=Path(manifest['root']).resolve()
    allowed={CATALOG,PROVENANCE,*map(db_relative,PLANS)}
    entries=manifest['files']
    if len({e['relative'] for e in entries})!=len(entries):raise ValueError('Duplicate targets')
    for e in entries:
        if e['relative'] not in allowed:raise ValueError('Target outside migration scope')
        target=(root/e['relative']).resolve()
        if not target.is_relative_to(root):raise ValueError('Target escapes worktree')
        expected=e['before'] if expected_state=='prepared' else e['after']
        if (sha(target) if target.exists() else None)!=expected:raise ValueError('Target drift: '+e['relative'])
        if e['before'] is not None and sha(Path(e['backup']))!=e['before']:raise ValueError('Backup drift')
        if expected_state=='prepared' and sha(Path(e['staged']))!=e['after']:raise ValueError('Staging drift')
        if target.suffix=='.db' and any(Path(str(target)+suffix).exists() for suffix in ('-wal','-shm','-journal')):
            raise ValueError('Active SQLite sidecar; stop writers before migration')
    return root,entries


def replace_file(source,target):
    import tempfile
    handle,name=tempfile.mkstemp(prefix=target.name+'.migration-',dir=target.parent)
    os.close(handle);temporary=Path(name)
    try:
        shutil.copyfile(source,temporary)
        os.replace(temporary,target)
    finally:
        if temporary.exists():temporary.unlink()


def restore_entry(root,e):
    target=root/e['relative']
    if sha(target)!=e['after']:raise ValueError('Concurrent change blocks rollback: '+e['relative'])
    if e['before'] is None:target.unlink()
    else:replace_file(Path(e['backup']),target)


def install(manifest):
    root,entries=checked_entries(manifest,'prepared')
    catalog=read(Path(next(e['staged'] for e in entries if e['relative']==CATALOG))) if manifest['databases'] else None
    for d in manifest['databases']:validate_database(Path(d['staged']),catalog,d['protected'])
    installed=[]
    try:
        for e in entries:
            target=root/e['relative']
            if (sha(target) if target.exists() else None)!=e['before']:raise ValueError('Concurrent target change')
            replace_file(Path(e['staged']),target);installed.append(e)
            if sha(target)!=e['after']:raise ValueError('Installed hash mismatch')
        for d in manifest['databases']:validate_database(root/d['relative'],catalog,d['protected'])
    except BaseException:
        for e in reversed(installed):restore_entry(root,e)
        raise
    manifest['state']='promoted'


def restore(manifest,*,apply=False):
    root,entries=checked_entries(manifest,'promoted')
    if apply:
        for e in reversed(entries):restore_entry(root,e)
        manifest['state']='restored'
    return {'verified_backups':len(entries),'apply':apply}


def normalized(value):
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items() if k not in {'id','group_id'}}
    if isinstance(value,list):return [normalized(v) for v in value]
    return ' '.join(unicodedata.normalize('NFKC',value).split()) if isinstance(value,str) else value


def compare_backend(root,original,staged):
    sys.path.insert(0,str(root/'Lab7B_Lab8B_ocr_system/src/ocr_system'))
    import lab8b_curriculum_db as dbmod
    questions=['หมวดวิชาศึกษาทั่วไปมีวิชาอะไรบ้าง','วิชาเลือกด้านภาษาและการสื่อสารมีวิชาอะไรให้เลือกบ้าง','วิชาเลือกหมวดวิชาศึกษาทั่วไปมีวิชาอะไรให้เลือกบ้าง','วิชาเลือกของหลักสูตรนี้มีอะไรบ้าง']
    result=[]
    for q in questions:
        with closing(dbmod.open_db(original,readonly=True)) as a,closing(dbmod.open_db(staged,readonly=True)) as b:
            old,new=dbmod.ask(a,q,verbose=False),dbmod.ask(b,q,verbose=False)
        match=not old.get('error') and not new.get('error') and normalized(old['rows'])==normalized(new['rows']) and normalized(old['answer'])==normalized(new['answer'])
        result.append({'question':q,'same_rows_and_answer':bool(match),'rows':len(new['rows'])})
    if not all(r['same_rows_and_answer'] for r in result):raise ValueError('Backend catalog answers differ')
    return result


def prepare(root,source,output):
    root=root.resolve();source=source.resolve();output=output.resolve()
    if root==source or output.exists() or not output.is_relative_to(root):raise ValueError('New preparation directory must be inside the target worktree')
    catalog_path=source/CATALOG;catalog=read(catalog_path)
    archive=source/'.superpowers/ge66-ocr-audit/results'
    candidate=read(archive/'final/candidate.json')['records']
    observations={};evidence_paths=[catalog_path,archive/'final/candidate.json',archive/'final/verified-summary.json']
    for path in (archive/'targeted/observations.json',archive/'literal/observations.json'):
        evidence_paths.append(path)
        for code,items in read(path).items():observations.setdefault(code,[]).extend(items)
    for code in ('90642209','90642210'):
        text=archive/('final/'+code+'-english.txt');image=text.with_suffix('.png')
        evidence_paths.extend([text,image]);r=next(r for r in candidate if r['code']==code)
        observations[code].append({'name_en':text.read_text(encoding='utf-8').strip(),'page':r['page'],'engine':'tesseract','source':str(text)})
    verified=verify_catalog(catalog,candidate,observations,read(archive/'final/verified-summary.json'))
    old=read(root/CATALOG)
    if {r['code'] for r in rows(old)}!={r['code'] for r in rows(catalog)}:raise ValueError('Existing catalog scope differs')
    output.mkdir(parents=True)
    manifest={'root':str(root),'state':'prepared','created':datetime.now().isoformat(),'source_evidence_hashes':{str(p):sha(p) for p in evidence_paths},'verified_records':303,'raw_traceable_fields':verified,'files':[],'databases':[],'comparisons':[]}
    def entry(relative,staged):
        target=root/relative;backup=output/'backup'/relative
        before=sha(target) if target.exists() else None
        if before is not None:
            backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,backup)
            if sha(backup)!=before:raise ValueError('Backup copy differs')
        manifest['files'].append({'relative':relative,'before':before,'after':sha(staged),'staged':str(staged),'backup':str(backup) if before else None})
    protected_paths=[*root.glob('Lab7B_Lab8B_ocr_system/runs/**/curriculum.db'),*root.glob('Lab9_evaluation/**/*gold*.json')]
    manifest['protected_files_before']={str(p.relative_to(root)):sha(p) for p in protected_paths}
    for plan in PLANS:
        relative=db_relative(plan);original=root/relative;staged=output/'staged'/relative
        if any(Path(str(original)+s).exists() for s in ('-wal','-shm','-journal')):raise ValueError('Stop SQLite writers before preparation')
        untouched=stage_database(original,staged,catalog);entry(relative,staged)
        manifest['databases'].append({'relative':relative,'staged':str(staged),'protected':untouched,'ge_courses':303})
        manifest['comparisons'].extend({'plan':plan,**r} for r in compare_backend(root,original,staged))
    staged=output/'staged'/CATALOG;staged.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(catalog_path,staged);entry(CATALOG,staged)
    provenance={'method':'image_only_ocr','edition':2566,'verified_records':303,'raw_ocr_traceable_field_values':909,'manual_fills':0,'reference_used_for_development_and_evaluation':True,'reference_used_as_ocr_prompt_or_field_fill':False,'accuracy_scope':'Historical full GE66 development verification; separate from GE64 frozen samples','migration_manifest':str(output/'manifest.json'),'source_catalog_sha256':sha(catalog_path),'backup_root':str(output/'backup'),'backend_matches':20,'backend_total':20,'databases':manifest['databases'],'source_evidence_hashes':manifest['source_evidence_hashes']}
    staged=output/'staged'/PROVENANCE;write(staged,provenance);entry(PROVENANCE,staged)
    for relative,before in manifest['protected_files_before'].items():
        if sha(root/relative)!=before:raise ValueError('Source target changed while preparing')
    checked_entries(manifest,'prepared');write(output/'manifest.json',manifest)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare');p.add_argument('--root',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    for name in ('install','restore'):
        p=commands.add_parser(name);p.add_argument('--manifest',type=Path,required=True)
        if name=='restore':p.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        m=prepare(args.root,args.source,args.output);print('Prepared',m['verified_records'],'records',m['raw_traceable_fields'],'raw fields',len(m['comparisons']),'backend matches')
    else:
        m=read(args.manifest)
        if args.command=='install':install(m);write(args.manifest,m)
        else:
            print(restore(m,apply=args.apply))
            if args.apply:write(args.manifest,m)
        print(m['state'])


if __name__=='__main__':main()
