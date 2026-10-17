#!/usr/bin/env python3
# custom-claude-glance — a 3-line, truecolor status line for Claude Code
# https://github.com/trongld230289/custom-claude-glance
#
# ╭ ✦ model  ·  effort ●●●○○  ·  ⎇ branch ← gốc  +add -del · n files · n uncommitted
# ├ ctx ━━━━━━━━━━━━━━ 28%  │ 5h ▰▱▱▱▱▱   5% ↻ 4h56  │ 7d ▰▰▱▱▱▱  25% ↻ 6d11h
# ╰ ↓ 276.9k in ↑ 663 out │ ◎ 273.4k cache 98% hit │ 42m session  ·  cache warm 54m
import json, os, re, subprocess, sys, tempfile, time, unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")  # cần cho Windows
except Exception:
    pass

d = json.load(sys.stdin)

# ═════════════════ màu truecolor ═════════════════
RST, BOLD = "\033[0m", "\033[1m"

def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def fg(h):
    r, g, b = rgb(h); return f"\033[38;2;{r};{g};{b}m"

def mix(a, b, t):
    a, b = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

def ramp(stops, t):
    t = max(0.0, min(1.0, t))
    seg = t * (len(stops) - 1)
    i = min(int(seg), len(stops) - 2)
    return mix(stops[i], stops[i + 1], seg - i)

def gradient(text, a, b):
    n = max(len(text) - 1, 1)
    return BOLD + "".join(fg(mix(a, b, i / n)) + ch for i, ch in enumerate(text)) + RST

HEAT = ["#34d399", "#a3e635", "#fbbf24", "#fb923c", "#f43f5e"]   # xanh → đỏ
RAIL = ["#f9a8d4", "#c4b5fd", "#93c5fd"]                         # màu thanh dọc bên trái
MUTED, FAINT, SEP_C = "#8b93a7", "#3a3f4b", "#4b5263"

def heat(p):
    return ramp(HEAT, (p or 0) / 100)

def bar(p, width, full="━", empty="━"):
    filled = round((p or 0) / 100 * width)
    if (p or 0) > 0:
        filled = max(filled, 1)  # có dùng thì luôn sáng ít nhất 1 ô
    out = ""
    for i in range(width):
        out += (fg(ramp(HEAT, i / max(width - 1, 1))) + full) if i < filled else (fg(FAINT) + empty)
    return out + RST

def link(url, text):
    return f"\033]8;;{url}\a{text}\033]8;;\a"

def left(ts):
    s = int(ts - time.time())
    if s <= 0:
        return "now"
    dd, h, m = s // 86400, (s % 86400) // 3600, (s % 3600) // 60
    return f"{dd}d{h}h" if dd else f"{h}h{m:02d}" if h else f"{m}m"

def k(n):
    n = n or 0
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.1f}k" if n >= 1e3 else str(int(n))

ANSI = re.compile(r"\x1b\[[0-9;]*m|\x1b\]8;;.*?\x07")

def vlen(s):
    """Độ rộng hiển thị (bỏ mã màu, chữ rộng tính 2)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in ANSI.sub("", s))

# ═════════════════ git (cache 5 giây) ═════════════════
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

def git(args, cwd):
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, timeout=2,
            encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
        ).stdout.strip()
    except Exception:
        return ""

BASES = ["main", "master", "develop", "dev"]

def is_sha(s):
    return len(s) >= 7 and all(c in "0123456789abcdef" for c in s)

def base_branch(cwd, branch):
    if not branch or branch in BASES or branch == "detached":
        return ""
    blog = git(["reflog", "show", f"refs/heads/{branch}", "--format=%gs"], cwd).splitlines()
    if blog and blog[-1].startswith("branch: Created from "):
        src = blog[-1][len("branch: Created from "):].replace("refs/heads/", "").replace("refs/remotes/", "")
        if src != "HEAD" and not is_sha(src):
            return src
    pre, suf = "checkout: moving from ", f" to {branch}"
    for line in reversed(git(["reflog", "show", "HEAD", "-n", "3000", "--format=%gs"], cwd).splitlines()):
        if line.startswith(pre) and line.endswith(suf):
            src = line[len(pre):-len(suf)]
            if src != branch and not is_sha(src):
                return src
            break
    best, best_n = "", None
    for cand in BASES + [f"origin/{b}" for b in BASES]:
        if not git(["rev-parse", "--verify", "--quiet", cand], cwd):
            continue
        n = git(["rev-list", "--count", f"{cand}..HEAD"], cwd)
        if n.isdigit() and (best_n is None or int(n) < best_n):
            best, best_n = cand.replace("origin/", ""), int(n)
    return best

def git_info(cwd, sid):
    tmp = tempfile.gettempdir()
    cache = os.path.join(tmp, f"claude-sl-{sid}.json")
    diff_file = os.path.join(tmp, f"claude-changes-{sid}.txt")
    try:
        if time.time() - os.path.getmtime(cache) < 5:
            with open(cache, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    info = {"branch": "", "base": "", "add": 0, "rem": 0, "files": 0, "dirty": 0, "names": [], "diff": diff_file}
    if git(["rev-parse", "--is-inside-work-tree"], cwd) == "true":
        info["branch"] = git(["branch", "--show-current"], cwd) or "detached"
        info["base"] = base_branch(cwd, info["branch"])
        # Thay đổi của cả nhánh: từ điểm tách khỏi nhánh gốc tới working tree (gồm cả phần chưa commit).
        # Không có nhánh gốc (đang ở main…) thì chỉ tính phần chưa commit so với HEAD.
        since = "HEAD"
        if info["base"]:
            for ref in (info["base"], "origin/" + info["base"]):
                mb = git(["merge-base", ref, "HEAD"], cwd)
                if mb:
                    since = mb
                    break
        info["dirty"] = len(git(["diff", "HEAD", "--name-only"], cwd).splitlines())
        changed = []
        for line in git(["diff", since, "--numstat"], cwd).splitlines():
            a, r, path = (line.split("\t") + ["", "", ""])[:3]
            a, r = int(a) if a.isdigit() else 0, int(r) if r.isdigit() else 0
            info["files"] += 1
            info["add"] += a
            info["rem"] += r
            path = path.split(" => ")[-1].strip("{}")  # file đổi tên: lấy tên mới
            changed.append((a + r, os.path.basename(path)))
        # file đổi nhiều nhất lên trước
        info["names"] = [n for _, n in sorted(changed, key=lambda x: -x[0])]
        if info["files"]:
            stat = git(["diff", since, "--stat"], cwd)
            full = git(["diff", since], cwd)
            with open(diff_file, "w", encoding="utf-8") as f:
                f.write(f"Branch: {info['branch']}" + (f" vs {info['base']} (incl. uncommitted)" if since != "HEAD" else " (uncommitted)") + f"\n\n{stat}\n\n{'=' * 60}\n\n{full}\n")
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(info, f)
    except Exception:
        pass
    return info

# ═════════════════ dữ liệu ═════════════════
cfg = os.environ.get("CLAUDE_CONFIG_DIR", "").rstrip("/\\")
acc = os.path.basename(cfg).replace(".claude-", "") if cfg else ""
if acc == ".claude":
    acc = ""

model = (d.get("model") or {}).get("display_name", "?")
effort = (d.get("effort") or {}).get("level")
cw = d.get("context_window") or {}
cu = cw.get("current_usage") or {}
pc = d.get("prompt_cache") or {}
pct = int(cw.get("used_percentage") or 0)
rl = d.get("rate_limits") or {}
five, week = rl.get("five_hour") or {}, rl.get("seven_day") or {}
cwd = (d.get("workspace") or {}).get("current_dir") or d.get("cwd") or os.getcwd()
g = git_info(cwd, d.get("session_id", "x"))
pr_url = (d.get("pr") or {}).get("url")

# ═════════════════ bố cục: lưới 3 hàng × 3 cột ═════════════════
# Chỉ dùng ký tự rộng đúng 1 ô ở mọi font (━ ● ↓ ↑ ◎ │) để các cột thẳng hàng.
dur_ms = (d.get("cost") or {}).get("total_duration_ms") or 0
cost = (d.get("cost") or {}).get("total_cost_usd")

def kf(n):
    return k(n).rjust(6)  # cố định 6 ô: số dài ra không đẩy lệch cột

def dur(ms):
    m = int(ms // 60000)
    return f"{m // 60}h{m % 60:02d}m" if m >= 60 else f"{m}m"

def meter(label, w, width, accent):
    if not w or w.get("used_percentage") is None:
        return ""
    p = w["used_percentage"]
    s = f"{fg(MUTED)}{label} {bar(p, width, '▰', '▱')} {fg(heat(p))}{BOLD}{p:>3.0f}%{RST}"
    if w.get("resets_at"):
        s += f" {fg(accent)}↻ {left(w['resets_at']):<5}{RST}"
    return s

# hàng 1
r1c0 = f"{fg('#f9a8d4')}✦{RST} " + gradient(model, "#f9a8d4", "#c4b5fd")
if acc:
    r1c0 += f" {fg('#f472b6')}@{acc}{RST}"
r1c1 = ""
if effort:
    lv = {"low": 1, "medium": 2, "high": 3, "xhigh": 4, "max": 5}.get(effort, 0)
    dots = "".join((fg(ramp(["#fde68a", "#f59e0b", "#f43f5e"], i / 4)) + "●") if i < lv else (fg(FAINT) + "●")
                   for i in range(5))
    r1c1 = f"{fg(MUTED)}{effort} {dots}{RST}"
r1c2 = ""
if g["branch"]:
    br = f"{fg('#5eead4')}{BOLD}⎇ {g['branch']}{RST}"
    if pr_url:
        br = link(pr_url, br)  # click branch → mở PR
    r1c2 = br
    if g.get("base"):
        r1c2 += f" {fg(MUTED)}← {fg('#99f6e4')}{g['base']}{RST}"
    if g["files"]:
        n = g["files"]
        ch = (f"{fg('#4ade80')}{BOLD}+{g['add']}{RST} {fg('#fb7185')}{BOLD}-{g['rem']}{RST}"
              f" {fg(MUTED)}· {n} file{'s' if n > 1 else ''}{RST}")
        r1c2 += "  " + link("file:///" + g["diff"].replace("\\", "/"), ch)  # Ctrl+click → xem diff đầy đủ
        if g.get("base") and g.get("dirty"):
            r1c2 += f" {fg(MUTED)}· {fg('#fbbf24')}{g['dirty']}{fg(MUTED)} uncommitted{RST}"

# hàng 2
r2c0 = f"{fg(MUTED)}ctx {bar(pct, 14)} {fg(heat(pct))}{BOLD}{pct:>3}%{RST}"
r2c1 = meter("5h", five, 6, "#67e8f9")
r2c2 = meter("7d", week, 6, "#a5b4fc")

# hàng 3
r3c0 = ""
if cw.get("total_input_tokens") or cw.get("total_output_tokens"):
    r3c0 = (f"{fg('#60a5fa')}↓ {BOLD}{kf(cw.get('total_input_tokens'))}{RST}{fg(MUTED)} in{RST} "
            f"{fg('#c084fc')}↑ {BOLD}{kf(cw.get('total_output_tokens'))}{RST}{fg(MUTED)} out{RST}")
cache_read, hit = cu.get("cache_read_input_tokens"), pc.get("hit_ratio")
r3c1 = ""
if cache_read is not None or hit is not None:
    r3c1 = f"{fg('#fbbf24')}◎ {BOLD}{kf(cache_read)}{RST}{fg(MUTED)} cache{RST}"
    if hit is not None:
        r3c1 += f" {fg(heat(100 - hit * 100))}{BOLD}{hit * 100:>3.0f}%{RST}{fg(MUTED)} hit{RST}"
r3c2 = ""
if dur_ms:
    r3c2 = f"{fg('#f0abfc')}{BOLD}{dur(dur_ms)}{RST}{fg(MUTED)} session{RST}"
# Cache còn "ấm" bao lâu: nhắn tiếp trước khi hết giờ thì đọc lại cache, đỡ tốn quota
exp = pc.get("expires_at")
if pc.get("caching_observed"):
    if pc.get("warm") and exp and exp > time.time():
        remain = exp - time.time()
        c = "#4ade80" if remain > 120 else "#fbbf24"  # sắp nguội → vàng
        cell = f"{fg(MUTED)}cache warm{RST} {fg(c)}{BOLD}{left(exp)}{RST}"
    else:
        cell = f"{fg(MUTED)}cache{RST} {fg('#60a5fa')}{BOLD}cold{RST}"
    r3c2 = f"{r3c2}  {fg(SEP_C)}·{RST}  {cell}" if r3c2 else cell

# Dòng 1 = tiêu đề, nối bằng dấu · (không căn cột)
DOT = f"  {fg(SEP_C)}·{RST}  "
out = [DOT.join(x for x in (r1c0, r1c1, r1c2) if x)]

# Dòng 2–3 = bảng 2 hàng, kẻ dọc │, các cột căn thẳng
grid = [r for r in ([r2c0, r2c1, r2c2], [r3c0, r3c1, r3c2]) if any(r)]
if grid:
    widths = [max(vlen(r[c]) for r in grid) for c in range(3)]
    GAP = f" {fg(SEP_C)}│{RST} "
    for r in grid:
        last = max(i for i in range(3) if r[i])
        cells = [r[c] + " " * (widths[c] - vlen(r[c])) if c < last else r[c] for c in range(last + 1)]
        out.append(GAP.join(cells))

# Thanh dọc bên trái ╭ ├ ╰, đổi màu hồng → tím → xanh
for i, line in enumerate(out):
    glyph = "◆" if len(out) == 1 else "╭" if i == 0 else "╰" if i == len(out) - 1 else "├"
    print(f"{fg(RAIL[min(i, len(RAIL) - 1)])}{glyph}{RST} {line}")
