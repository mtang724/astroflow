"""Setup check: a fake PixInsight installation and settings slot 1 in tmp_path, never the user's."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from astroflow import doctor, pi, settings
from astroflow.api.app import Services, create_app

TOKEN = "test-token"
H = {"Authorization": f"Bearer {TOKEN}"}
LICENSE = "SECRET-LICENSE-VALUE"


def write_pi_settings(path, version="1.9.4-0.1690", licensed=doctor.RC_TOOLS, gaia=()):
    """A settings slot in PixInsight's XSDT format with only the entries the check reads."""
    modules = "".join(f'<i k="{t}"><v k="{t}.email" t="s">me@example.com</v><v k="{t}.license" t="s">{LICENSE}</v></i>'
                      for t in licensed)
    modules += '<i k="Gaia">' + "".join(f'<v k="DR3SPDatabaseFilePath{i:02d}" t="s">{p}</v>'
                                        for i, p in enumerate(gaia)) + "</i>"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<?xml version="1.0" encoding="UTF-8"?><xsdt version="1.0" xmlns="http://www.pixinsight.com/xsdt">'
                    f'<v k="LastVersion" t="s">{version}</v><i k="ModuleData">{modules}</i></xsdt>', encoding="utf-8")


@pytest.fixture
def machine(tmp_settings, monkeypatch):
    """A complete setup: PixInsight with scripts and the RC tools, Gaia files, a data root. Tests remove pieces."""
    tmp_path, store = tmp_settings
    root = tmp_path / "PixInsight"
    exe = root / "bin" / "PixInsight.exe"
    for f in [exe, root / "src/scripts/BatchPreprocessing/WBPP.js", root / "src/scripts/AdP/ImageSolver.js",
              *(root / "bin" / f"{t}-pxm.dll" for t in doctor.RC_TOOLS)]:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"")
    gaia = [tmp_path / "GaiaSP" / f"gdr3sp-1.0.0-s-0{i}.xpsd" for i in (1, 2)]
    for f in gaia:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"")
    pis = tmp_path / "Pleiades" / "core-001-pxi.settings"
    write_pi_settings(pis, gaia=[f.as_posix() for f in gaia])
    (tmp_path / "Astro").mkdir()
    monkeypatch.setattr(doctor, "pi_settings_files", lambda: [pis])
    monkeypatch.setattr(doctor, "usual_programs", lambda: [])
    monkeypatch.setattr(pi, "running_instances", lambda: [])
    s = settings.get()
    s.astro_root = (tmp_path / "Astro").as_posix()
    s.pixinsight_exe = exe.as_posix()
    s.pixinsight_scripts = (root / "src" / "scripts").as_posix()
    settings.save(s)
    store["DeepSeek"] = "sk-test"
    yield SimpleNamespace(tmp=tmp_path, root=root, exe=exe, pis=pis, gaia=gaia, store=store)


def by_id(report):
    return {c["id"]: c for c in report["checks"]}


def test_complete_setup_is_ready(machine):
    report = doctor.run()
    assert report["ready"] and report["notes"] == []
    assert {c["id"]: c["status"] for c in report["checks"]} == {
        "pixinsight": "ok", "scripts": "ok", "rc_astro": "ok", "gaia": "ok", "data_root": "ok", "runs_dir": "ok", "ai": "ok"}
    assert by_id(report)["pixinsight"]["summary"].startswith("1.9.4")
    assert "2 个数据库文件" in by_id(report)["gaia"]["summary"]


def test_nothing_installed_explains_every_step(machine, monkeypatch):
    s = settings.get()
    s.pixinsight_exe = (machine.tmp / "nowhere" / "PixInsight.exe").as_posix()
    s.pixinsight_scripts = (machine.tmp / "nowhere" / "scripts").as_posix()
    s.astro_root = (machine.tmp / "NewAstro").as_posix()
    settings.save(s)
    machine.store.clear()
    monkeypatch.setattr(doctor, "pi_settings_files", lambda: [machine.tmp / "absent.settings"])
    report = doctor.run()
    c = by_id(report)
    assert not report["ready"]
    assert c["pixinsight"]["status"] == "missing" and c["pixinsight"]["steps"] and c["pixinsight"]["links"]
    assert [a["kind"] for a in c["pixinsight"]["actions"]] == ["pick_file"]
    assert c["rc_astro"]["status"] == "unknown" and c["gaia"]["status"] == "unknown"
    assert c["data_root"]["actions"][0] == {"kind": "create_folder", "label": "创建这个文件夹",
                                            "setting": "astro_root", "value": {"astro_root": str(machine.tmp / "NewAstro")},
                                            "tab": None}
    assert c["ai"]["level"] == "optional" and c["ai"]["status"] == "missing"
    assert c["ai"]["actions"][0]["kind"] == "open_settings"


def test_pixinsight_found_elsewhere_offers_its_paths(machine, monkeypatch):
    s = settings.get()
    s.pixinsight_exe = "C:/wrong/PixInsight.exe"
    s.pixinsight_scripts = "C:/wrong/scripts"
    settings.save(s)
    monkeypatch.setattr(doctor, "usual_programs", lambda: [machine.exe])
    report = doctor.run()
    c = by_id(report)
    apply = c["pixinsight"]["actions"][0]
    assert apply["kind"] == "apply" and apply["value"] == {
        "pixinsight_exe": machine.exe.as_posix(), "pixinsight_scripts": (machine.root / "src" / "scripts").as_posix()}
    assert c["rc_astro"]["status"] == "ok"            # checked on the installation that was found


def test_rc_tools_missing_or_not_activated(machine):
    (machine.root / "bin" / "StarXTerminator-pxm.dll").unlink()
    c = by_id(doctor.run())["rc_astro"]
    assert c["status"] == "missing" and "StarXTerminator" in c["summary"]
    assert doctor.RC_REPOSITORIES == [s for step in c["steps"] for s in step["code"]]

    (machine.root / "bin" / "StarXTerminator-pxm.dll").write_bytes(b"")
    write_pi_settings(machine.pis, licensed=("BlurXTerminator",), gaia=[f.as_posix() for f in machine.gaia])
    report = doctor.run()
    c = by_id(report)["rc_astro"]
    assert not report["ready"] and c["status"] == "missing"
    assert "NoiseXTerminator、StarXTerminator" in c["summary"] and "BlurXTerminator" not in c["summary"]


def test_gaia_missing_is_recommended_not_blocking(machine):
    write_pi_settings(machine.pis)
    report = doctor.run()
    assert report["ready"] and by_id(report)["gaia"]["status"] == "missing"
    write_pi_settings(machine.pis, gaia=[machine.gaia[0].as_posix(), (machine.tmp / "moved.xpsd").as_posix()])
    c = by_id(doctor.run())["gaia"]
    assert c["status"] == "warn" and "1 个找不到" in c["summary"]


def test_old_pixinsight_and_open_gui(machine, monkeypatch):
    write_pi_settings(machine.pis, version="1.8.9-2", licensed=())
    monkeypatch.setattr(pi, "running_instances", lambda: [{"pid": 1, "name": "PixInsight"}])
    report = doctor.run()
    assert by_id(report)["pixinsight"]["status"] == "missing" and "1.8.9" in by_id(report)["pixinsight"]["summary"]
    assert report["notes"]                             # activation is only saved when the GUI closes


def test_runs_dir_with_spaces(machine):
    s = settings.get()
    s.runs_dir = (machine.tmp / "has space" / "runs").as_posix()
    settings.save(s)
    c = by_id(doctor.run())["runs_dir"]
    assert c["status"] == "missing" and c["actions"][0]["setting"] == "runs_dir"


def test_resolve_pixinsight_exe(tmp_path):
    app = tmp_path / "PixInsight" / "PixInsight.app"
    exe = app / "Contents" / "MacOS" / "PixInsight"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert doctor.resolve_pixinsight_exe(str(app)) == exe.as_posix()
    assert doctor.resolve_pixinsight_exe(str(tmp_path / "PixInsight")) == exe.as_posix()
    assert doctor.resolve_pixinsight_exe("C:/x/PixInsight.exe") == "C:/x/PixInsight.exe"


def test_api_reports_without_licenses_and_creates_data_root(machine):
    client = TestClient(create_app(TOKEN, services=Services()), base_url="http://127.0.0.1:8765")
    r = client.get("/api/setup", headers=H)
    assert r.status_code == 200 and r.json()["ready"] and LICENSE not in r.text
    assert client.get("/api/setup").status_code == 401

    target = machine.tmp / "Astro 2"
    r = client.post("/api/setup/data-root", json={"path": str(target)}, headers=H)
    assert r.status_code == 200 and by_id(r.json())["data_root"]["status"] == "ok"
    assert (target / "In Processing").is_dir() and settings.get().astro_root == str(target)
    assert client.post("/api/setup/data-root", json={"path": "relative/dir"}, headers=H).status_code == 400

    app = machine.tmp / "Mac" / "PixInsight.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "MacOS" / "PixInsight").write_bytes(b"")
    r = client.patch("/api/settings", json={"pixinsight_exe": str(app)}, headers=H)
    assert r.json()["pixinsight_exe"].endswith("PixInsight.app/Contents/MacOS/PixInsight")
