#!/usr/bin/env python3
"""claude-glance installer (cross-platform, no dependencies).

  python install.py                     # global: your Claude Code account (~/.claude)
  python install.py --all-accounts      # global: ~/.claude and every ~/.claude-* account
  python install.py --project [PATH]    # only one repo (default: current folder)
  python install.py --uninstall [...]   # remove, same scope flags as above
"""
import argparse, glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "glance.py")
HOME = os.path.expanduser("~")
SHARED_DIR = os.path.join(HOME, ".claude", "glance")
MARK = "glance.py"


def fwd(p):
    # Claude Code on Windows may run the command through Git Bash, which eats backslashes
    return p.replace("\\", "/")


def interpreter():
    """Python command to put in settings.json. Must not contain spaces (no quoting games)."""
    exe = sys.executable or ""
    if exe and " " not in exe:
        return fwd(exe)
    if os.name == "nt" and shutil.which("py"):
        return "py -3"
    return "python" if os.name == "nt" else "python3"


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        txt = f.read().strip()
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        sys.exit(f"x {path} is not valid JSON ({e}). Fix it, then run the installer again.")


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak-glance")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def account_dirs(all_accounts):
    if all_accounts:
        dirs = [os.path.join(HOME, ".claude")]
        dirs += sorted(p for p in glob.glob(os.path.join(HOME, ".claude-*")) if os.path.isdir(p))
        return dirs
    return [os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")]


def prev_file(settings_file):
    return os.path.join(os.path.dirname(settings_file), ".glance-previous-statusline.json")


def git_exclude(proj):
    """Keep the copied script out of git without touching tracked files (.git/info/exclude)."""
    ex = os.path.join(proj, ".git", "info", "exclude")
    if not os.path.isdir(os.path.dirname(ex)):
        return
    line = ".claude/glance/"
    cur = open(ex, encoding="utf-8").read() if os.path.exists(ex) else ""
    if line not in cur.split():
        with open(ex, "a", encoding="utf-8") as f:
            f.write(("" if cur.endswith("\n") or not cur else "\n") + line + "\n")
        print(f"+ git       {line} added to .git/info/exclude")


def uses_glance(settings_file):
    cmd = ((load(settings_file).get("statusLine") or {}).get("command") or "")
    return MARK in cmd


def demo(script):
    now = int(time.time())
    sample = {
        "model": {"display_name": "Opus 5.5"}, "effort": {"level": "high"},
        "context_window": {"used_percentage": 31, "total_input_tokens": 310400, "total_output_tokens": 1520,
                           "current_usage": {"cache_read_input_tokens": 307400}},
        "prompt_cache": {"hit_ratio": 0.98, "warm": True, "caching_observed": True, "expires_at": now + 3240},
        "rate_limits": {"five_hour": {"used_percentage": 16, "resets_at": now + 16800},
                        "seven_day": {"used_percentage": 26, "resets_at": now + 558000}},
        "cost": {"total_duration_ms": 2520000},
        "workspace": {"current_dir": os.getcwd()}, "session_id": "glance-demo",
    }
    try:
        out = subprocess.run([sys.executable, script], input=json.dumps(sample), capture_output=True,
                             text=True, encoding="utf-8", timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            print("\nPreview:\n" + out.stdout)
        else:
            print("\n! The script did not run cleanly:\n" + (out.stderr or "(no output)"))
    except Exception as e:
        print(f"\n! Could not run a preview: {e}")


def install(script_dir, settings_files):
    if not os.path.exists(SRC):
        sys.exit(f"x glance.py not found next to install.py ({HERE})")
    os.makedirs(script_dir, exist_ok=True)
    dst = os.path.join(script_dir, "glance.py")
    shutil.copy2(SRC, dst)
    print(f"+ script    {dst}")
    cmd = f'{interpreter()} "{fwd(dst)}"'
    for s in settings_files:
        data = load(s)
        prev = data.get("statusLine")
        if prev and MARK not in (prev.get("command") or ""):
            # remember the status line you had before, so --uninstall can put it back
            with open(prev_file(s), "w", encoding="utf-8") as f:
                json.dump(prev, f, indent=2, ensure_ascii=False)
        data["statusLine"] = {"type": "command", "command": cmd, "refreshInterval": 30}
        save(s, data)
        print(f"+ settings  {s}" + ("   (old status line saved, --uninstall restores it)" if prev and MARK not in (prev.get("command") or "") else ""))
    print(f"\n  command:  {cmd}")
    demo(dst)
    print("Done. Claude Code picks this up automatically; numbers appear after the first reply.")


def uninstall(script_dir, settings_files, shared):
    for s in settings_files:
        if os.path.exists(s) and uses_glance(s):
            data = load(s)
            pf = prev_file(s)
            if os.path.exists(pf):
                with open(pf, encoding="utf-8") as f:
                    data["statusLine"] = json.load(f)
                os.remove(pf)
                note = "   (restored your previous status line)"
            else:
                data.pop("statusLine", None)
                note = ""
            save(s, data)
            print(f"- settings  {s}{note}")
    still_used = shared and any(uses_glance(os.path.join(d, "settings.json")) for d in account_dirs(True))
    if os.path.isdir(script_dir) and not still_used:
        shutil.rmtree(script_dir)
        print(f"- script    {script_dir}")
    elif still_used:
        print(f"  kept {script_dir} (another account still uses it)")
    print("Done.")


def main():
    ap = argparse.ArgumentParser(description="Install the claude-glance status line for Claude Code.")
    ap.add_argument("--project", nargs="?", const=os.getcwd(), metavar="PATH",
                    help="install only for this repo (default: current folder)")
    ap.add_argument("--all-accounts", action="store_true",
                    help="global install for ~/.claude and every ~/.claude-* account")
    ap.add_argument("--uninstall", action="store_true", help="remove instead of install")
    a = ap.parse_args()

    if a.project:
        proj = os.path.abspath(a.project)
        script_dir = os.path.join(proj, ".claude", "glance")
        # settings.local.json = personal to you, not committed to git
        files = [os.path.join(proj, ".claude", "settings.local.json")]
        shared = False
        print(f"Scope: project  {proj}")
        if not a.uninstall:
            git_exclude(proj)
    else:
        script_dir = SHARED_DIR
        files = [os.path.join(d, "settings.json") for d in account_dirs(a.all_accounts)]
        shared = True
        print("Scope: global" + ("  (all accounts)" if a.all_accounts else ""))

    if a.uninstall:
        uninstall(script_dir, files, shared)
    else:
        install(script_dir, files)


if __name__ == "__main__":
    main()
