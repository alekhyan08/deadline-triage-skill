#!/usr/bin/env python3
"""Deadline triage helper (original, AI-assisted drafting); stdlib only, no external code copied.

Pure supplied-data processing. No network, credential lookup or mail mutation.
"""
import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo


MONTHS={m:i for i,m in enumerate(('january','february','march','april','may','june','july','august','september','october','november','december'),1)}
MONTHS.update({m[:3]:i for m,i in list(MONTHS.items())})
MONTHS['sept']=9
WEEKDAYS={d:i for i,d in enumerate(('monday','tuesday','wednesday','thursday','friday','saturday','sunday'))}
WEEKDAYS.update({d[:3]:i for d,i in list(WEEKDAYS.items())})
DATE=(r'(?:(?P<wd>[A-Za-z]{3,9})\.?,?\s+)?(?:(?P<d1>\d{1,2})\s+(?P<m1>[A-Za-z]{3,9})\.?,?\s+(?P<y1>\d{4})'
      r'|(?P<m2>[A-Za-z]{3,9})\.?\s+(?P<d2>\d{1,2}),?\s+(?P<y2>\d{4})|(?P<iso>\d{4}-\d{2}-\d{2}))\b')
PHRASE=re.compile(r'\b(?:due|deadline)\b(?:\s+(?:is|date))?\s*(?:by|on|before|:)?\s*(?:'+DATE+r'|(?P<rel>today|tomorrow)\b)',re.I)
ANY_DATE=re.compile(DATE,re.I)


def _phrase_date(match,received_day):
    """One explicit date from a due/deadline phrase, or ValueError when it is not exact."""
    rel=match.groupdict().get('rel')
    if rel:
        return received_day+timedelta(days=int(rel.lower()=='tomorrow'))
    if match.group('iso'):value=date.fromisoformat(match.group('iso'))
    else:
        month=(match.group('m1') or match.group('m2')).lower().rstrip('.')
        if month not in MONTHS:raise ValueError()
        value=date(int(match.group('y1') or match.group('y2')),MONTHS[month],int(match.group('d1') or match.group('d2')))
    weekday=match.group('wd')
    if weekday and weekday.lower() in WEEKDAYS and WEEKDAYS[weekday.lower()]!=value.weekday():raise ValueError()
    return value


def _stamp(value):
    if not isinstance(value,str):raise ValueError('Explicit timestamp required')
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Timestamp must have an offset')
    return stamp


def triage(request):
    if not isinstance(request,dict):raise ValueError('JSON object required')
    as_of=_stamp(request['as_of']);zone=ZoneInfo(request['timezone']);today=as_of.astimezone(zone).date()
    messages=request.get('messages')
    if not isinstance(messages,list) or len(messages)>2000:raise ValueError('Bounded complete message list required')
    seen=set();threads={}
    for row in messages:
        if not isinstance(row,dict):raise ValueError('Message object required')
        for key in ('id','thread','body','subject'):
            if not isinstance(row.get(key),str):raise ValueError('Message fields must be strings')
        if not row['id'] or not row['thread'] or row['id'] in seen:raise ValueError('Unique nonempty source and thread IDs required')
        seen.add(row['id'])
        if any(type(row.get(k,False)) is not bool for k in ('draft','unread','starred')):raise ValueError('Explicit boolean flags required')
        if row.get('draft'):continue
        if row.get('body_complete') is False or row.get('body_range',{}).get('complete') is False:raise ValueError('Retrieve complete message bodies first')
        received=_stamp(row['received_at'])
        if received>as_of:raise ValueError('Message timestamp is later than review time')
        threads.setdefault(row['thread'],[]).append((received,row))
    output=[]
    for thread,entries in threads.items():
        entries.sort(key=lambda e:e[0])
        received,row=entries[-1]
        if len(entries)>1 and entries[-2][0]==received:raise ValueError('Ambiguous latest thread correction')
        text=row['body']
        resolved=re.search(r'^\s*Status:\s*(resolved|cancelled|canceled|no action)\s*$',text,re.I|re.M)
        labels=re.findall(r'^\s*(?:Deadline|Due):\s*(.*?)\s*$',text,re.I|re.M)
        dates=set();invalid=False
        for label in labels:
            try:
                lower=label.lower()
                if lower in ('today','tomorrow'):
                    value=received.astimezone(zone).date()+timedelta(days=int(lower=='tomorrow'))
                elif re.fullmatch(r'\d{4}-\d{2}-\d{2}',label):value=date.fromisoformat(label)
                else:raise ValueError()
                dates.add(value)
            except ValueError:invalid=True
        phrases=[];label_dates=set(dates)
        for match in PHRASE.finditer(text):
            try:
                value=_phrase_date(match,received.astimezone(zone).date())
                for other in ANY_DATE.finditer(text[match.end():match.end()+60]):
                    if _phrase_date(other,received.astimezone(zone).date())!=value:raise ValueError()
                dates.add(value)
                if value not in label_dates:phrases.append(match.group(0).strip())
            except ValueError:invalid=True
        deadline=None;evidence=None
        if resolved:priority='resolved';evidence=resolved.group(0).strip()
        elif len(dates)==1 and not invalid:
            deadline=next(iter(dates));days=(deadline-today).days
            priority='overdue' if days<0 else 'due_today' if days==0 else 'due_soon' if days<=2 else 'scheduled'
            evidence=' | '.join(labels+phrases)
        else:priority='needs_review'
        output.append({'source_id':row['id'],'thread':thread,'received_at':received.isoformat(),
            'subject':row['subject'],'priority':priority,'deadline':str(deadline) if deadline else None,
            'evidence':evidence,'thread_has_unread':any(r.get('unread',False) for _,r in entries),
            'thread_starred':any(r.get('starred',False) for _,r in entries),
            'superseded_source_ids':[r['id'] for _,r in entries[:-1]]})
    rank={p:i for i,p in enumerate(('overdue','due_today','due_soon','needs_review','scheduled','resolved'))}
    output.sort(key=lambda r:(rank[r['priority']],not r['thread_starred'],r['deadline'] or '',r['source_id']))
    return {'local_date':str(today),'timezone':str(zone),'items':output,
            'method':'Latest delivered thread evidence; explicit deadline/status labels and full-date due phrases only. No mail actions.'}


LABELS={'overdue':'OVERDUE','due_today':'DUE TODAY','due_soon':'DUE SOON','scheduled':'SCHEDULED','needs_review':'NEEDS REVIEW','resolved':'RESOLVED'}


def format_text(result):
    """One readable line per thread, most urgent first; excerpts only, never instructions."""
    lines=[f"Deadline triage as of {result['local_date']} ({result['timezone']}): {len(result['items'])} thread(s)"]
    for number,item in enumerate(result['items'],1):
        subject=' '.join(item['subject'].split())[:90]
        when=item['deadline'] or 'no explicit date'
        star='* ' if item['thread_starred'] else ''
        evidence=f'  evidence: "{item["evidence"][:80]}"' if item['evidence'] and item['priority']!='resolved' else ''
        lines.append(f"{number}. {LABELS[item['priority']]}  {when}  {star}{subject}  [{item['source_id']}]{evidence}")
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path)
    parser.add_argument('--text',action='store_true',help='print a readable ranked list instead of JSON')
    args=parser.parse_args()
    try:
        if args.input:
            with args.input.open(encoding='utf-8') as source:raw=source.read(262145)
        else:raw=sys.stdin.read(262145)
        if len(raw.encode())>262144:raise ValueError('Input too large; no truncation')
        result=triage(json.loads(raw))
    except (ValueError,KeyError,TypeError,OSError):
        print(json.dumps({'success':False,'error':'Invalid, incomplete or unsupported export; no action taken.'}))
        return 2
    print(format_text(result) if args.text else json.dumps({'success':True,**result},ensure_ascii=True));return 0

if __name__=='__main__':raise SystemExit(main())
