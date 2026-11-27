import os
import requests

REPO = os.getenv("GH_REPO", "naykokoko135-pixel/NEXORA-MYANMAR-RECAP")
REF = os.getenv("GH_REF", "main")
API = "https://api.github.com"


def _h():
    return {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}


def dispatch(workflow, inputs):
    r = requests.post(f"{API}/repos/{REPO}/actions/workflows/{workflow}/dispatches", headers=_h(),
                      json={"ref": REF, "inputs": {k: str(v) for k, v in inputs.items()}}, timeout=30)
    if r.status_code != 204:
        raise RuntimeError(f"dispatch {r.status_code}: {r.text[:200]}")


def runs(n=5):
    r = requests.get(f"{API}/repos/{REPO}/actions/runs", headers=_h(), params={"per_page": n}, timeout=30)
    r.raise_for_status()
    return r.json()["workflow_runs"]


def cancel(run_id):
    return requests.post(f"{API}/repos/{REPO}/actions/runs/{run_id}/cancel", headers=_h(), timeout=30).status_code == 202


def rerun(run_id):
    return requests.post(f"{API}/repos/{REPO}/actions/runs/{run_id}/rerun-failed-jobs", headers=_h(), timeout=30).status_code == 201
