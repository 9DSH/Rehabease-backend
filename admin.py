"""
Minimal admin panel for managing doctor accounts.

Protected by a single shared username/password (HTTP Basic Auth -- the
browser shows its own native login prompt, no session/cookie code needed).
Set REHABEASE_ADMIN_USER / REHABEASE_ADMIN_PASSWORD env vars in production.

Visit /admin in a browser.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth
import db_models
from database import get_db

router = APIRouter(prefix="/admin", dependencies=[Depends(auth.require_admin)])


class DoctorCreate(BaseModel):
    firstname: str
    lastname: str
    username: str
    password: str


class DoctorOut(BaseModel):
    id: str
    firstname: str
    lastname: str
    username: str
    enable: bool


@router.get("/api/doctors")
def list_doctors(db: Session = Depends(get_db)):
    doctors = db.query(db_models.Doctor).all()
    return [
        DoctorOut(id=d.id, firstname=d.firstname, lastname=d.lastname,
                  username=d.username, enable=d.enable)
        for d in doctors
    ]


@router.post("/api/doctors")
def create_doctor(body: DoctorCreate, db: Session = Depends(get_db)):
    if db.query(db_models.Doctor).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    doctor = db_models.Doctor(
        firstname=body.firstname,
        lastname=body.lastname,
        username=body.username,
        password_hash=auth.hash_password(body.password),
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return DoctorOut(id=doctor.id, firstname=doctor.firstname, lastname=doctor.lastname,
                      username=doctor.username, enable=doctor.enable)


@router.delete("/api/doctors/{doctor_id}")
def delete_doctor(doctor_id: str, db: Session = Depends(get_db)):
    doctor = db.query(db_models.Doctor).filter_by(id=doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    db.delete(doctor)
    db.commit()
    return {"ok": True}


@router.patch("/api/doctors/{doctor_id}/toggle")
def toggle_doctor(doctor_id: str, db: Session = Depends(get_db)):
    doctor = db.query(db_models.Doctor).filter_by(id=doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor.enable = not doctor.enable
    db.commit()
    return DoctorOut(id=doctor.id, firstname=doctor.firstname, lastname=doctor.lastname,
                      username=doctor.username, enable=doctor.enable)


@router.get("", response_class=HTMLResponse)
def admin_page():
    return _PAGE_HTML


_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RehabEase Admin</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f5f7; margin: 0; padding: 40px 20px; color: #1c1e21;
  }
  .wrap { max-width: 720px; margin: 0 auto; }
  h1 { font-size: 22px; margin-bottom: 4px; }
  p.sub { color: #656d76; margin-top: 0; margin-bottom: 28px; font-size: 14px; }
  .card {
    background: #fff; border: 1px solid #e1e4e8; border-radius: 10px;
    padding: 20px; margin-bottom: 24px;
  }
  .card h2 { font-size: 15px; margin: 0 0 16px; color: #24292f; }
  form.inline { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  form.inline input { grid-column: span 1; }
  form.inline button { grid-column: span 2; }
  input {
    padding: 9px 11px; border: 1px solid #d0d7de; border-radius: 6px;
    font-size: 14px; width: 100%;
  }
  button {
    padding: 9px 14px; border: none; border-radius: 6px; font-size: 14px;
    background: #1f6feb; color: white; cursor: pointer; font-weight: 500;
  }
  button:hover { background: #1a5fd0; }
  button.danger { background: #cf222e; }
  button.danger:hover { background: #a40e26; }
  button.secondary { background: #6e7781; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #eef0f2; }
  th { color: #656d76; font-weight: 600; font-size: 12px; text-transform: uppercase; }
  td.actions { text-align: right; white-space: nowrap; }
  td.actions button { margin-left: 6px; padding: 5px 10px; font-size: 12px; }
  .badge { padding: 2px 8px; border-radius: 20px; font-size: 12px; font-weight: 500; }
  .badge.on { background: #dafbe1; color: #1a7f37; }
  .badge.off { background: #ffebe9; color: #cf222e; }
  .empty { color: #656d76; font-size: 14px; padding: 12px 0; }
  #msg { font-size: 13px; margin-top: 10px; min-height: 18px; }
  #msg.error { color: #cf222e; }
  #msg.ok { color: #1a7f37; }
</style>
</head>
<body>
<div class="wrap">
  <h1>RehabEase Admin</h1>
  <p class="sub">Manage doctor accounts</p>

  <div class="card">
    <h2>Add doctor</h2>
    <form class="inline" id="createForm">
      <input name="firstname" placeholder="First name" required>
      <input name="lastname" placeholder="Last name" required>
      <input name="username" placeholder="Username" required>
      <input name="password" type="password" placeholder="Password" required>
      <button type="submit">Create doctor</button>
    </form>
    <div id="msg"></div>
  </div>

  <div class="card">
    <h2>Doctors</h2>
    <table id="table" style="display:none">
      <thead>
        <tr><th>Name</th><th>Username</th><th>Status</th><th></th></tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div class="empty" id="empty">No doctors yet.</div>
  </div>
</div>

<script>
async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

function showMsg(text, isError) {
  const el = document.getElementById('msg');
  el.textContent = text;
  el.className = isError ? 'error' : 'ok';
  setTimeout(() => { el.textContent = ''; }, 4000);
}

async function loadDoctors() {
  const doctors = await api('/admin/api/doctors');
  const tbody = document.getElementById('tbody');
  const table = document.getElementById('table');
  const empty = document.getElementById('empty');
  tbody.innerHTML = '';

  if (doctors.length === 0) {
    table.style.display = 'none';
    empty.style.display = 'block';
    return;
  }
  table.style.display = 'table';
  empty.style.display = 'none';

  for (const d of doctors) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${d.firstname} ${d.lastname}</td>
      <td>${d.username}</td>
      <td><span class="badge ${d.enable ? 'on' : 'off'}">${d.enable ? 'Active' : 'Disabled'}</span></td>
      <td class="actions">
        <button class="secondary" data-toggle="${d.id}">${d.enable ? 'Disable' : 'Enable'}</button>
        <button class="danger" data-delete="${d.id}">Delete</button>
      </td>
    `;
    tbody.appendChild(tr);
  }

  tbody.querySelectorAll('[data-delete]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this doctor? This cannot be undone.')) return;
      try {
        await api(`/admin/api/doctors/${btn.dataset.delete}`, { method: 'DELETE' });
        showMsg('Doctor deleted');
        loadDoctors();
      } catch (e) { showMsg(e.message, true); }
    });
  });

  tbody.querySelectorAll('[data-toggle]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await api(`/admin/api/doctors/${btn.dataset.toggle}/toggle`, { method: 'PATCH' });
        loadDoctors();
      } catch (e) { showMsg(e.message, true); }
    });
  });
}

document.getElementById('createForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.target;
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    await api('/admin/api/doctors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    showMsg('Doctor created');
    form.reset();
    loadDoctors();
  } catch (e) { showMsg(e.message, true); }
});

loadDoctors();
</script>
</body>
</html>
"""
