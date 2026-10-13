"""astroflow command line.

    python -m astroflow doctor                     # what is missing on this computer and how to install it
    python -m astroflow status                     # every target in In Processing and how far it got
    python -m astroflow organize [--apply] [--refresh] [--source <folder>] [--copy]
    python -m astroflow stack <target>|--all       # WBPP for targets without a master (skips missing darks)
    python -m astroflow process <target> [--recipe R] [--from STAGE | --stage STAGE] [--set a.b.c=v ...]
    python -m astroflow comet <target> [--reuse-sxt]  # comet: stack on stars + nucleus, then the comet recipe
    python -m astroflow agent [<target>] [--task "..."]
    python -m astroflow refs <target>
    python -m astroflow video <file.mp4> [--out DIR]
"""
import argparse
import json
import sys



def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):          # messages are Chinese: never crash on a non-UTF-8 console
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(prog="astroflow", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("status")
    o = sub.add_parser("organize")
    o.add_argument("--apply", action="store_true")
    o.add_argument("--refresh", action="store_true", help="give staged targets the library frames they lack")
    o.add_argument("--source", action="append", help="folder to import (default: new folders in the data root)")
    o.add_argument("--copy", action="store_true", help="copy lights instead of moving them")
    s = sub.add_parser("stack")
    s.add_argument("target", nargs="?")
    s.add_argument("--all", action="store_true")
    p = sub.add_parser("process")
    p.add_argument("target")
    p.add_argument("--recipe")
    p.add_argument("--from", dest="start")
    p.add_argument("--stage")
    p.add_argument("--set", action="append")
    c = sub.add_parser("comet")
    c.add_argument("target")
    c.add_argument("--reuse-sxt", action="store_true")
    c.add_argument("--stack-only", action="store_true", help="stop after astroflow.comet (no PixInsight finish)")
    g = sub.add_parser("agent")
    g.add_argument("target", nargs="?")
    g.add_argument("--task", default="")
    g.add_argument("--max-pi-jobs", type=int, default=30)
    r = sub.add_parser("refs")
    r.add_argument("target")
    v = sub.add_parser("video")
    v.add_argument("file")
    v.add_argument("--out")
    a = ap.parse_args(argv)

    if a.cmd == "doctor":
        from . import doctor
        report = doctor.run()
        doctor.print_report(report)
        return 0 if report["ready"] else 1
    if a.cmd == "status":
        from .agent import tools
        for t in tools.list_targets():
            print(f"{t['night']:<10} {t['target']:<10} L{t['lights']:>3} D{t['darks']:>3} B{t['bias']:>3} F{t['flats']:>3}  "
                  f"master={'Y' if t['master'] else '-'}  {t['recipe'] or '':<22} {','.join(t['stages_done'])}"
                  f"{'  FINISHED' if t['finished'] else ''}")
    elif a.cmd == "organize":
        from . import organize
        plan, notes = organize.build_plan(sources=a.source, refresh=a.refresh)
        organize.print_plan(plan, notes)
        if a.apply:
            organize.apply_plan(plan, move_lights=not a.copy)
    elif a.cmd == "stack":
        from . import wbpp
        from .agent import tools
        targets = [t for t in tools.list_targets() if not t["master"]] if a.all else [{"path": str(tools.resolve(a.target)), "darks": 1}]
        for t in targets:
            if a.all and t["darks"] == 0:
                print(f"skip {t['target']}: no darks yet (python organize.py --refresh --apply after shooting them)")
                continue
            r = wbpp.run(t["path"])
            r.pop("highlights", None)
            print(json.dumps(r, ensure_ascii=False, indent=1))
    elif a.cmd == "process":
        from . import pipeline
        from .agent import tools
        for rec in pipeline.run(tools.resolve(a.target), a.recipe, a.start, a.stage, pipeline.parse_sets(a.set)):
            print(json.dumps({k: rec[k] for k in ("stage", "seconds", "previews")}, ensure_ascii=False))
    elif a.cmd == "comet":
        from pathlib import Path

        from . import comet, pipeline
        from .agent import tools
        target = tools.resolve(a.target)
        post = Path(target) / "Post"
        frames = post / "frames"
        if not list(frames.glob("*.fits")):
            comet.convert_registered(target, frames)
        d = comet.run(frames, post, reuse_sxt=a.reuse_sxt)
        print(json.dumps({k: d[k] for k in ("motion", "reference", "white_balance", "stack")}, ensure_ascii=False, indent=1))
        if not a.stack_only:
            for rec in pipeline.run(target, "comet", start="linear", master=post / "comet_stack.fits"):
                print(json.dumps({k: rec[k] for k in ("stage", "seconds", "previews")}, ensure_ascii=False))
    elif a.cmd == "agent":
        from .agent import run
        print(run.run(a.task or ("按流程完整处理这个目标并给出成品。" if a.target else "列出可以处理的目标并逐个处理。"),
                      a.target, max_pi_jobs=a.max_pi_jobs))
    elif a.cmd == "refs":
        from . import references
        from .agent import tools
        d = references.fetch(tools.resolve(a.target).name, n=6, fov_radius=1.44)
        print(json.dumps({g: [(e["title"], e["author"], e["likes"]) for e in d[g]] for g in ("best", "peer")}, ensure_ascii=False, indent=1))
    elif a.cmd == "video":
        from . import video
        print(json.dumps(video.analyze(a.file, a.out), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
