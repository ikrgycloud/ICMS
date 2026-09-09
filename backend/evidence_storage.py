"""Provider-neutral local development evidence storage adapter."""
import hashlib, os, re
from pathlib import Path

class EvidenceStorageAdapter:
    def __init__(self, root=None):
        provider=os.environ.get("EVIDENCE_STORAGE_PROVIDER","local").lower()
        environment=os.environ.get("ICMS_ENVIRONMENT","development").lower()
        if environment in {"production","prod"} and provider=="local":
            raise RuntimeError("Local evidence storage is not permitted in production")
        if provider!="local": raise RuntimeError(f"Evidence storage provider '{provider}' is not configured")
        self.root=Path(root or os.environ.get("EVIDENCE_STORAGE_DIR","./evidence-store")).resolve()
    def _safe_key(self,key):
        if not key or Path(key).is_absolute() or "\\" in key or ".." in Path(key).parts: raise ValueError("Unsafe evidence storage key")
        path=(self.root/key).resolve()
        if self.root not in path.parents: raise ValueError("Unsafe evidence storage key")
        return path
    def normalize_filename(self,filename):
        name=Path(filename or "evidence").name
        name=re.sub(r"[^A-Za-z0-9._ -]","_",name).strip(". ")
        return (name or "evidence")[:180]
    def put(self, content:bytes, filename:str, tenant_id:str=""):
        """Store evidence under a tenant partition to prevent cross-tenant key reuse."""
        digest=hashlib.sha256(content).hexdigest()
        tenant=re.sub(r"[^A-Za-z0-9_-]", "_", tenant_id or "legacy")[:120]
        key=f"{tenant}/{digest[:2]}/{digest}-{self.normalize_filename(filename)}"
        path=self._safe_key(key); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(content)
        return key,digest
    def get(self,key:str): return self._safe_key(key).read_bytes()
    def delete(self,key:str):
        path=self._safe_key(key)
        if path.exists(): path.unlink()
