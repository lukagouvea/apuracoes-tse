"""Export official histories and explicitly labelled section reconstruction to HTML."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import pandas as pd
from projecao.download import atomic_json,sha256
from projecao.study import load_study
from projecao.totalization import read_totalization,reconstruct_first_totalization


def build(root,output):
    root=Path(root);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    artifact=output.parent/'apuracao';artifact.mkdir(parents=True,exist_ok=True)
    config=json.load(open('configs/elections.json'));elections={};frames=[]
    for year in load_study()['evaluation_years']:
        cfg=config[str(year)];out=root/'processed'/str(year)
        prep=json.loads((out/'preparation.json').read_text());totals=json.loads((out/'totals-check.json').read_text())
        if totals['status']!='matched':raise ValueError(f'{year}: final totals not independently validated')
        e={'name_a':cfg['name_a'],'name_b':cfg['name_b'],'final_a':prep['votes_a'],'final_b':prep['votes_b'],'points':[],'kind':'final_only','has_sections':False}
        sources=list((root/'raw'/str(year)/'totals').glob('*.zip'));f=None;manifest=None
        if sources:
            if len(sources)!=1:raise ValueError('Expected exactly one totalization ZIP per year')
            source=sources[0];manifest=json.loads((root/'manifests'/f'{year}-totals-{source.name}.json').read_text())
            if manifest['status']!='complete' or sha256(source)!=manifest['sha256']:raise ValueError('Source checksum mismatch')
            f=read_totalization(source,year,prep['candidate_a'],prep['candidate_b'])
            e.update(kind='official_totalization',has_sections=True,adapter='Série nacional acumulada do TSE.' if year==2022 else 'Incrementos oficiais por município/zona agregados nacionalmente por horário.')
        elif year==2018 and (out/'section_timing.parquet').exists():
            timing=json.loads((out/'chronology.json').read_text())
            if not timing.get('usable') or not timing.get('reconstructed_from_final_votes'):raise ValueError('First-totalization timing not audited')
            if sha256(out/'section_timing.parquet')!=timing.get('timing_sha256'):raise ValueError('Timing checksum mismatch')
            f=reconstruct_first_totalization(root,year)
            source_record=timing['source_manifests'][0]
            manifest=json.loads((root/source_record['manifest']).read_text())
            if manifest['sha256']!=source_record['sha256']:raise ValueError('Timing source provenance mismatch')
            e.update(kind='reconstructed_first_totalization',has_sections=True,late_sections=timing['late_sections'],
                adapter='Reconstrução com votos finais por seção e horário oficial da primeira totalização. Não reproduz correções intermediárias nem o instante de publicação na internet. Oito registros de fevereiro de 2019 são preservados.')
        if f is not None:
            last=f.iloc[-1]
            if (int(last.votes_a),int(last.votes_b))!=(prep['votes_a'],prep['votes_b']):raise ValueError(f'{year}: endpoint differs from audited totals')
            f['kind']=e['kind'];frames.append(f)
            start=f.timestamp.iloc[0];seconds=(f.timestamp-start).dt.total_seconds().astype('int64')
            e.update(start=start.isoformat(),sections_total=int(last.sections_total) if e['has_sections'] else None,
                source=manifest['url'],source_sha256=manifest['sha256'],
                points=[[int(t),int(n) if pd.notna(n) else None,int(a),int(b)] for t,n,a,b in zip(seconds,f.sections,f.votes_a,f.votes_b)])
            print(f'{year}: {len(f):,} updates, {e["kind"]}, endpoint verified',flush=True)
        elections[str(year)]=e
    payload={'study':load_study(),'generated_at':datetime.now().strftime('%d/%m/%Y'),'timestamp_timezone':None,'elections':elections}
    pd.concat(frames,ignore_index=True).to_parquet(artifact/'curves.parquet',index=False,compression='zstd')
    atomic_json(artifact/'curves.json',payload)
    template=Path('templates/apuracao.html').read_text()
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    output.write_text(template.replace('__ELECTION_DATA__',encoded))
    atomic_json(artifact/'manifest.json',{'html_sha256':sha256(output),'parquet_sha256':sha256(artifact/'curves.parquet'),
        'source_code':{str(p):sha256(p) for p in [Path(__file__),Path('src/projecao/totalization.py'),Path('src/projecao/timing.py'),Path('src/projecao/study.py'),Path('configs/study.json'),Path('templates/apuracao.html')]},
        'series':{y:{k:v for k,v in e.items() if k!='points'}|{'updates':len(e['points'])} for y,e in elections.items()}})
    print(f'HTML: {output} ({output.stat().st_size/1024:.1f} KiB)',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='/data/tse',type=Path);p.add_argument('--output',default='reports/apuracao.html',type=Path)
    a=p.parse_args();build(a.root,a.output)
