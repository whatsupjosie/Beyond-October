from __future__ import annotations
import json, secrets, time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
Role = Literal['portable','resident']
@dataclass(frozen=True)
class NodeIdentity:
    node_id:str; role:Role; created_at:float
    def to_dict(self): return {'node_id':self.node_id,'role':self.role,'created_at':self.created_at}
    @classmethod
    def from_dict(cls,value): return cls(str(value['node_id']), value['role'], float(value['created_at']))
def _default_node_id(role:str)->str: return f'{role}-{secrets.token_hex(4)}'
def load_or_create_identity(path:str|Path, role:Role, node_id:str|None=None)->NodeIdentity:
    path=Path(path)
    if path.exists():
        existing=NodeIdentity.from_dict(json.loads(path.read_text()))
        if existing.role != role:
            raise ValueError(f'identity file {path} was created as role={existing.role!r}, but this process was started with role={role!r}. Refusing to silently relabel an existing node identity.')
        return existing
    identity=NodeIdentity(node_id or _default_node_id(role), role, time.time())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(identity.to_dict(), indent=2))
    return identity
