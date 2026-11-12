"""Owner-configurable Blackbox archive policy; no deletion or migration here.

The archive manager must consume this policy when implemented. Wallet custody
is independent. Flagged archives, live journals and pending deliveries cannot
be made eligible by changing these settings.
"""
from __future__ import annotations
import calendar
from datetime import datetime,timedelta,timezone
import json
import shutil

from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
from .chat_commit_store import ChatCommitStore


class PolicyConflict(ValueError):
    pass


class ArchiveLimits(BaseModel):
    model_config=ConfigDict(extra='forbid')
    storage_limit_bytes: int=Field(default=5_000_000_000,gt=0,le=2**63-1,strict=True)
    retention_value: int=Field(default=6,gt=0,le=3_650_000,strict=True)
    retention_unit: Literal['days','weeks','months','years']='months'

    def expires_at(self,created: datetime) -> datetime:
        if created.tzinfo is None or created.utcoffset() is None:
            raise ValueError('Creation date must include a timezone')
        created=created.astimezone(timezone.utc)
        if self.retention_unit in {'days','weeks'}:
            days=self.retention_value*(7 if self.retention_unit=='weeks' else 1)
            return created+timedelta(days=days)
        months=self.retention_value*(12 if self.retention_unit=='years' else 1)
        year,month=divmod(created.year*12+created.month-1+months,12)
        month+=1
        day=min(created.day,calendar.monthrange(year,month)[1])
        return created.replace(year=year,month=month,day=day)

    @model_validator(mode='after')
    def representable_expiry(self):
        try:self.expires_at(datetime.now(timezone.utc))
        except (ValueError,OverflowError):raise ValueError('Retention period exceeds the supported calendar range') from None
        return self


class PolicyUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision: int=Field(ge=0,strict=True)
    storage_limit_bytes: int | None=Field(default=None,gt=0,le=2**63-1,strict=True)
    retention_value: int | None=Field(default=None,gt=0,le=3_650_000,strict=True)
    retention_unit: Literal['days','weeks','months','years'] | None=None

    @model_validator(mode='after')
    def nonempty_patch(self):
        fields=self.model_fields_set-{'expected_revision'}
        if not fields or any(getattr(self,key) is None for key in fields):
            raise ValueError('Supply at least one non-null archive limit')
        return self


class ArchivePolicyStore:
    def __init__(self,data_dir):
        self.store=ChatCommitStore(data_dir)
        with self.store._connection(writing=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS blackbox_archive_policy (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                revision INTEGER NOT NULL, limits_json TEXT NOT NULL,
                updated_at TEXT NOT NULL, actor TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS blackbox_archive_policy_history (
                revision INTEGER PRIMARY KEY, event_json TEXT NOT NULL,
                witnessed INTEGER NOT NULL DEFAULT 0 CHECK(witnessed IN (0,1)))''')
            db.execute('''INSERT OR IGNORE INTO blackbox_archive_policy VALUES (1,0,?,?,?)''',
                (ArchiveLimits().model_dump_json(),datetime.now(timezone.utc).isoformat(),'system:defaults'))

    @staticmethod
    def _view(row):
        return {'revision':row['revision'],**ArchiveLimits.model_validate_json(row['limits_json']).model_dump(),
                'updated_at':row['updated_at'],'updated_by':row['actor'],
                'defaults_provisional':True,'flagged_records_never_delete':True,
                'active_and_pending_records_protected':True,'automatic_cleanup_enabled':False,
                'scope':'blackbox_event_archives','wallet_custody_affected':False}

    def read(self):
        with self.store._connection() as db:
            return self._view(db.execute('SELECT * FROM blackbox_archive_policy WHERE singleton=1').fetchone())

    def update(self,body: PolicyUpdate,actor: str):
        patch=body.model_dump(exclude_unset=True);expected=patch.pop('expected_revision')
        with self.store._connection(writing=True) as db:
            row=db.execute('SELECT * FROM blackbox_archive_policy WHERE singleton=1').fetchone()
            if row['revision']!=expected:raise PolicyConflict('Archive settings changed; reload before saving')
            old=ArchiveLimits.model_validate_json(row['limits_json'])
            new=ArchiveLimits.model_validate({**old.model_dump(),**patch})
            if new==old:return {**self._view(row),'changed':False}
            revision=row['revision']+1;stamp=datetime.now(timezone.utc).isoformat()
            event={'change_id':f'archive-policy:{revision}','revision':revision,'actor':actor,
                   'changed_at':stamp,'before':old.model_dump(),'after':new.model_dump()}
            db.execute('UPDATE blackbox_archive_policy SET revision=?,limits_json=?,updated_at=?,actor=? WHERE singleton=1',
                       (revision,new.model_dump_json(),stamp,actor))
            db.execute('INSERT INTO blackbox_archive_policy_history(revision,event_json) VALUES (?,?)',
                       (revision,json.dumps(event,ensure_ascii=False,sort_keys=True)))
            updated=db.execute('SELECT * FROM blackbox_archive_policy WHERE singleton=1').fetchone()
            return {**self._view(updated),'changed':True}

    def deliver_audits(self,witness):
        # At-least-once audit delivery, identified by immutable change_id.
        # Re-delivery records observations only; it never reapplies settings.
        with witness._lock, self.store._connection(writing=True) as db:
            for row in db.execute('SELECT revision,event_json FROM blackbox_archive_policy_history WHERE witnessed=0 ORDER BY revision LIMIT 64').fetchall():
                event=json.loads(row['event_json'])
                if not witness.record_event('blackbox.archive_policy_changed',source='blackbox',actor=event['actor'],data=event):
                    break
                db.execute('UPDATE blackbox_archive_policy_history SET witnessed=1 WHERE revision=?',(row['revision'],))
            return db.execute('SELECT count(*) FROM blackbox_archive_policy_history WHERE witnessed=0').fetchone()[0]

    def capacity(self):
        limits=self.read()
        usage=shutil.disk_usage(self.store.root)
        return {**limits,'disk_free_bytes':usage.free,'disk_total_bytes':usage.total,
                'capacity_scope':'host_data_directory_volume',
                'limit_exceeds_current_free_space':limits['storage_limit_bytes']>usage.free,
                'preallocated':False,'archive_usage_bytes':None,
                'usage_note':'Archive catalog and cleanup are not enabled; this limit does not reserve device space.'}
