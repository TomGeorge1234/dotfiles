#!/usr/bin/env python3
"""A fast, dependency-free Slurm dashboard for the current user."""
from __future__ import annotations

import argparse, getpass, os, re, shutil, subprocess, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from statistics import median

TIMEOUT = 4
RESET = "\033[0m"
ANSI = {"cyan":"\033[1;36m", "green":"\033[1;32m", "yellow":"\033[1;33m",
        "red":"\033[1;31m", "dim":"\033[2m", "bold":"\033[1m",
        "blue":"\033[1;34m"}

def run(args: list[str]) -> tuple[str, str]:
    exe = shutil.which(args[0])
    if not exe: return "", f"{args[0]} is not installed"
    try:
        p = subprocess.run([exe, *args[1:]], text=True, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return "", f"{args[0]} timed out after {TIMEOUT}s"
    if p.returncode:
        lines = (p.stderr or p.stdout).strip().splitlines()
        return "", lines[-1] if lines else f"{args[0]} failed"
    return p.stdout.strip(), ""

def paint(text: str, style: str, enabled: bool) -> str:
    return f"{ANSI[style]}{text}{RESET}" if enabled else text

def gpu_count(tres: str) -> int:
    return sum(map(int, re.findall(r"(?:^|,)gres/gpu(?:/[^=,]+)?=(\d+)", tres)))

def requested_gpus(gres: str) -> int:
    return sum(int(m.group(1)) for x in gres.split(",")
               if (m := re.search(r"(?:^|/)gpu(?::[^:,]+)?:(\d+)(?:\(|$)", x)))

def gpu_types(gres: str) -> set[str]:
    """Return requested GPU types; '*' denotes an untyped GPU request."""
    types: set[str] = set()
    for item in gres.split(","):
        match = re.search(r"(?:^|/)gpu(?::([^:,]+))?:(\d+)(?:\(|$)", item)
        if match:
            types.add(match.group(1) or "*")
    return types

def fmt_number(value: str) -> str:
    try: return f"{float(value):.3f}"
    except ValueError: return value or "—"

def duration(seconds: float) -> str:
    seconds = max(0, int(seconds)); days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600); minutes = seconds // 60
    return f"{days}d {hours}h" if days else f"{hours}h {minutes}m" if hours else f"{minutes}m"

def elapsed_seconds(value: str) -> int | None:
    """Parse Slurm [days-]hours:minutes:seconds elapsed values."""
    match = re.fullmatch(r"(?:(\d+)-)?(\d+):(\d+):(\d+)", value)
    if not match:
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

def clock_duration(seconds: float) -> str:
    seconds = round(seconds); days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600); minutes, seconds = divmod(seconds, 60)
    return f"{days}-{hours:02d}:{minutes:02d}:{seconds:02d}" if days else f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def eta(value: str) -> str:
    if not value or value in {"N/A", "Unknown", "(null)"}: return ""
    try:
        start = datetime.fromisoformat(value).astimezone()
        return f"in {duration((start-datetime.now().astimezone()).total_seconds())} · {start:%a %H:%M}"
    except ValueError: return value

def bar(used: int, total: int, width: int = 24) -> str:
    filled = round(width * used / total) if total else 0
    return "█" * filled + "░" * (width - filled)

def completion_histogram(records: list[tuple], now: datetime, window: timedelta,
                         bins_count: int, base_color: str,
                         recent_color: str | None = None, recent_bins: int = 1,
                         color: bool = True) -> str:
    """Render completion counts and visibly highlight the most recent bins."""
    start = now - window
    bins = [0] * bins_count
    bin_seconds = window.total_seconds() / bins_count
    for ended, *_ in records:
        index = int((ended - start).total_seconds() // bin_seconds)
        if 0 <= index < bins_count:
            bins[index] += 1
    peak = max(bins, default=0)
    glyphs = " ▁▂▃▄▅▆▇█"
    chart = []
    for index, count in enumerate(bins):
        glyph = glyphs[(count * 8 + peak - 1) // peak] if count and peak else " "
        shade = (recent_color if recent_color and index >= bins_count - recent_bins
                 else base_color)
        chart.append(paint(glyph, shade, color))
    return "".join(chart)

def section(title: str, color: bool) -> None:
    print(f"\n{paint(title.upper(), 'cyan', color)}")

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", help="show only this job ID")
    ap.add_argument("--user", help="show jobs and fair-share data for this user")
    ap.add_argument("-p", "--partition", help="restrict jobs and nodes to a partition")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    args = ap.parse_args()
    user = args.user or os.environ.get("USER") or getpass.getuser()
    color = sys.stdout.isatty() and not args.no_color and "NO_COLOR" not in os.environ
    filters = (["-j", args.job] if args.job else []) + (["-p", args.partition] if args.partition else [])
    commands = {
        "share": ["sshare", "-u", user, "-n", "-P", "-o", "Account,User,NormShares,EffectvUsage,FairShare"],
        # Kept separate because some sites allow a user's association but hide peers.
        "peers": ["sshare", "-a", "-n", "-P", "-o", "Account,User,NormShares,EffectvUsage,FairShare"],
        "nodes": ["scontrol", "show", "nodes", "-o"],
        # Use the site's own availability monitor for the cluster-wide idle
        # counts; Slurm node totals alone include GPUs that may be reserved.
        "availability": ["savail"],
        "jobs": ["squeue", *filters, "-u", user, "-h", "-o", "%i|%T|%P|%j|%b|%Q|%M|%l|%r"],
        # Keep the dashboard compact by showing arrays as ranges above, but use
        # expanded elements here for the live-task count (relevant to Slurm's
        # per-user job limit).
        "job_count": ["squeue", *filters, "-u", user, "-h", "-r", "-o", "%i"],
        "starts": ["squeue", *filters, "-u", user, "-h", "--start", "-o", "%i|%S"],
        "competition": ["squeue", "-h", "-t", "PD", "-o", "%i|%u|%P|%b|%Q"],
        # Do not use -X: array-task records can disappear behind an active array
        # parent. Fetch all outcomes and filter locally; accounting state updates
        # can also lag briefly behind squeue.
        "completed": ["sacct", "-u", user, "-S", "now-7days",
                      "-n", "-P", "-o", "JobIDRaw,JobName%50,Partition,AllocTRES,Elapsed,End,State"],
    }
    with ThreadPoolExecutor(max_workers=8) as pool:
        fs = {k: pool.submit(run, v) for k, v in commands.items()}
        results = {k: f.result() for k, f in fs.items()}

    now = datetime.now().astimezone(); scope = f" · partition {args.partition}" if args.partition else ""
    title = f" SLURM · {user}{scope} "; width = max(66, len(title)+2)
    print(paint("╭"+"─"*(width-2)+"╮", "cyan", color))
    print(paint("│", "cyan", color)+paint(title.ljust(width-2), "bold", color)+paint("│", "cyan", color))
    stamp = f" {now:%a %Y-%m-%d · %H:%M %Z} "
    print(paint("╰"+stamp+"─"*(width-len(stamp)-2)+"╯", "cyan", color))
    errors: list[str] = []

    starts_out, start_err=results["starts"]
    starts=dict(line.split("|",1) for line in starts_out.splitlines() if "|" in line)
    if start_err: errors.append(start_err)
    out, err=results["jobs"]
    if err: errors.append(err)
    competition_out, competition_err = results["competition"]
    competitors = []
    if not competition_err:
        for line in competition_out.splitlines():
            fields = line.split("|", 4)
            if len(fields) == 5:
                peer_job, peer_user, peer_partition, peer_gres, peer_priority = fields
                try: peer_priority_value = int(peer_priority)
                except ValueError: continue
                competitors.append((peer_job, peer_user, peer_partition,
                                    gpu_types(peer_gres), peer_priority_value))
    job_count_out, job_count_err = results["job_count"]
    job_count = len(job_count_out.splitlines()) if not job_count_err else None
    jobs_title = f"Your jobs · {job_count} total" if job_count is not None else "Your jobs"
    section(jobs_title, color)
    if err: print(paint("  ◌ unavailable", "dim", color))
    elif not out: print(paint("  ✓ no matching jobs", "green", color))
    else:
        job_width = min(32, max(11, *(len(line.split("|", 1)[0]) for line in out.splitlines())))
        name_width = min(30, max(4, *(len(line.split("|", 4)[3]) for line in out.splitlines()
                                       if len(line.split("|", 4)) >= 4)))
        print(f"  {'JOB':<{job_width}} {'NAME':<{name_width}} {'STATE':<9} {'AHEAD':>6}  {'TIME':<13} ETA / REASON")
        for line in out.splitlines():
            f=line.split("|",8)
            if len(f)!=9: continue
            job,state,partition,name,gres,priority,elapsed,limit,reason=f
            style="green" if state=="RUNNING" else "yellow" if state=="PENDING" else "dim"
            detail=(eta(starts.get(job,"")) or f"waiting: {reason}") if state=="PENDING" else "—"
            ahead = "—"
            if state == "PENDING" and not competition_err:
                mine = gpu_types(gres)
                try: my_priority = int(priority)
                except ValueError: my_priority = -1
                ahead = str(sum(1 for peer_job, _, peer_partition, peer_types, peer_priority in competitors
                                if peer_job != job and peer_partition == partition
                                and peer_priority > my_priority
                                and (not mine or not peer_types or "*" in mine or "*" in peer_types or mine & peer_types)))
            job_text = job if len(job) <= job_width else job[:job_width-1] + "…"
            print(f"  {job_text:<{job_width}} {name:<{name_width}.{name_width}} {paint(state,style,color):<18} {ahead:>6}  "
                  f"{(elapsed+'/'+limit):<13.13} {detail}")

    section("Recent job outcomes · last 24 hours", color)
    completed_out, completed_err = results["completed"]
    if completed_err:
        errors.append(completed_err)
        print(paint("  ◌ accounting data unavailable", "dim", color))
    else:
        cutoff_week = datetime.now().astimezone() - timedelta(days=7)
        completed = []
        terminal_states = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY",
                           "NODE_FAIL", "PREEMPTED", "BOOT_FAIL", "DEADLINE", "REVOKED"}
        for line in completed_out.splitlines():
            fields = [field.strip() for field in line.rstrip("|").split("|", 6)]
            if len(fields) != 7:
                continue
            job, name, partition, tres, elapsed, ended, state = fields
            # sacct includes batch/extern job steps; retain allocations and array tasks.
            if "." in job:
                continue
            try:
                end_time = datetime.fromisoformat(ended).astimezone()
            except ValueError:
                continue
            base_state = state.split()[0].split("+")[0]
            if base_state in terminal_states and end_time >= cutoff_week:
                completed.append((end_time, job, name, partition, gpu_count(tres), elapsed, base_state))
        completed.sort(reverse=True)
        # Once an array parent completes sacct may return both the parent and all
        # tasks. The tasks are the actual runs, so omit that synthetic parent row.
        array_parents = {job.split("_", 1)[0] for _, job, *_ in completed if "_" in job}
        completed = [record for record in completed
                     if not ("_" not in record[1] and record[1] in array_parents)]
        if not completed:
            print(paint("  ◌ no terminal job records in the last 7 days", "dim", color))
        else:
            cutoff_day = now - timedelta(hours=24)
            recent = [record for record in completed if record[0] >= cutoff_day]
            successful = [record for record in recent if record[-1] == "COMPLETED"]
            hour_chart = completion_histogram(completed, now, timedelta(hours=1), 48, "blue", color=color)
            day_chart = completion_histogram(completed, now, timedelta(hours=24), 48, "yellow", "blue", 2, color)
            week_chart = completion_histogram(completed, now, timedelta(days=7), 48, "green", "yellow", 7, color)
            print("  Completions · local time · bars show jobs per interval")
            hour_count = sum(record[0] >= now - timedelta(hours=1) for record in completed)
            labels = [f"Last hour ({hour_count})",
                      f"Last 24 hrs ({len(recent)})",
                      f"Last 7 days ({len(completed)})"]
            label_width = max(map(len, labels))
            for label, chart in zip(labels, (hour_chart, day_chart, week_chart)):
                print(f"  {label:<{label_width}} |{chart}| Now")
            print(paint(f"  ✓ {len(successful)} jobs completed in the last 24 hours", "green", color))
            groups: dict[str, list[tuple]] = defaultdict(list)
            for record in successful:
                groups[record[2]].append(record)
            if groups:
                print(f"    {'JOB NAME':<32} {'COUNT':>5}  {'AVERAGE TIME':>12}  {'LATEST':>7}")
                for name, records in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
                    timings = [seconds for record in records
                               if (seconds := elapsed_seconds(record[5])) is not None]
                    average = clock_duration(sum(timings) / len(timings)) if timings else "—"
                    latest = max(record[0] for record in records)
                    print(f"    {name:<32.32} {len(records):>5}  {average:>12}  {latest:%H:%M}")
            failures = [record for record in recent if record[-1] != "COMPLETED"]
            if failures:
                by_state: dict[str, int] = defaultdict(int)
                for record in failures: by_state[record[-1]] += 1
                summary = " · ".join(f"{state.lower()} {count}" for state, count in sorted(by_state.items()))
                noun = "job" if len(failures) == 1 else "jobs"
                print(paint(f"  ! {len(failures)} {noun} did not complete successfully: {summary}", "red", color))
                failure_job_width = min(32, max(15, *(len(record[1]) for record in failures)))
                print(f"    {'JOB':<{failure_job_width}} {'STATE':<14} {'ELAPSED':<12} {'ENDED':<8} NAME")
                for ended, job, name, partition, gpus, elapsed, state in failures:
                    job_text = job if len(job) <= failure_job_width else job[:failure_job_width-1] + "…"
                    print(f"    {job_text:<{failure_job_width}} {paint(state,'red',color):<23} "
                          f"{elapsed:<12.12} {ended:%H:%M}    {name}")

    section("Fair-share", color)
    out, err = results["share"]
    if err: errors.append(err); print(paint("  ◌ unavailable", "dim", color))
    else:
        rows = [x[:5] for line in out.splitlines()
                if len(x := [p.strip() for p in line.rstrip("|").split("|")]) >= 5 and x[1] == user]
        peers_out, peers_err = results["peers"]
        associations = [x[:5] for line in peers_out.splitlines()
                        if len(x := [p.strip() for p in line.rstrip("|").split("|")]) >= 5]
        if rows:
            print(f"  {'ACCOUNT':<20} {'YOUR SCORE':>10}  {'RANK':<22} {'ACCOUNT MEDIAN':>14} {'USE/SHARE':>10}")
            for account, _, shares, usage, score in rows:
                value = None
                try:
                    value=float(score); style="green" if value>=.5 else "yellow" if value>=.2 else "red"
                    score_text=paint(f"{value:.3f}", style, color)
                except ValueError: score_text=score or "—"
                peers = []
                for peer_account, peer_user, _, _, peer_score in associations:
                    if peer_account == account and peer_user:
                        try: peers.append(float(peer_score))
                        except ValueError: pass
                if peers and value is not None:
                    rank = 1 + sum(peer > value for peer in peers)
                    better_pct = round(100 * (len(peers) - rank) / len(peers))
                    standing = f"top {better_pct}%" if better_pct >= 50 else f"bottom {100-better_pct}%"
                    peer_median = median(peers)
                    position = f"#{rank} of {len(peers)} · {standing}"
                    median_text = f"{peer_median:.3f}"
                    comparison = ((value / peer_median - 1) * 100) if peer_median else None
                else: position = "peer data unavailable"; median_text = "—"; comparison = None
                try:
                    ratio = float(usage) / float(shares)
                    ratio_text = f"{ratio:.2f}×"
                    ratio_style = "green" if ratio <= 1 else "yellow" if ratio <= 2 else "red"
                    ratio_text = paint(ratio_text, ratio_style, color)
                except (ValueError, ZeroDivisionError): ratio_text = "—"
                print(f"  {account:<20.20} {score_text:>19}  {position:<22.22} {median_text:>14} {ratio_text:>19}")
                if comparison is not None:
                    relation = "above" if comparison >= 0 else "below"
                    print(paint(f"  Your score is {abs(comparison):.0f}% {relation} the median for {account} · higher score is better", "dim", color))
        else: print(paint("  ◌ no user association returned", "dim", color))
        if peers_err:
            print(paint("  Peer data is hidden or unavailable; showing your raw association only.", "dim", color))

    section("Cluster GPUs", color)
    out, err = results["nodes"]
    avail_out, avail_err = results["availability"]
    availability = []
    if avail_err:
        print(paint("  Unreserved GPU availability (savail): unavailable", "dim", color))
    else:
        for line in avail_out.splitlines():
            match = re.match(r"^\s*(\S+)\s+(\d+)\s*/\s*(\d+)\s*$", line)
            if match:
                availability.append((match.group(1), int(match.group(2)), int(match.group(3))))
        if not availability:
            print(paint("  Unreserved GPU availability (savail): no GPU counts returned", "dim", color))
    if err: errors.append(err); print(paint("  ◌ unavailable", "dim", color))
    else:
        configured=allocated=gpu_nodes=unavailable=0
        for line in out.splitlines():
            parts=re.search(r"Partitions=(\S+)", line)
            if args.partition and (not parts or args.partition not in parts.group(1).split(",")): continue
            cfg=re.search(r"CfgTRES=(\S+)", line); alloc=re.search(r"AllocTRES=(\S+)", line); state=re.search(r"State=(\S+)", line)
            count=gpu_count(cfg.group(1)) if cfg else 0
            if not count: continue
            node_allocated=gpu_count(alloc.group(1)) if alloc else 0
            node_unavailable=count if state and re.search(r"DOWN|DRAIN|FAIL|MAINT", state.group(1)) else 0
            gpu_nodes+=1; configured+=count; allocated+=node_allocated; unavailable+=node_unavailable
        if availability:
            idle_total = sum(idle for _, idle, _ in availability)
            tracked_total = sum(total for _, _, total in availability)
            idle_pct = 100 * idle_total / tracked_total if tracked_total else 0
            idle_style = "red" if idle_pct < 10 else "yellow" if idle_pct < 30 else "green"
            print(f"  {paint(bar(idle_total,tracked_total), idle_style, color)}  {idle_total}/{tracked_total} unreserved idle GPUs (savail) · {idle_pct:.0f}%")
            model_line = "  " + "  ".join(
                paint(f"{model} {idle}/{total}", "dim", color) if idle == 0 else f"{model} {idle}/{total}"
                for model, idle, total in availability)
            print(model_line)

    if errors:
        section("Warnings", color)
        for message in dict.fromkeys(errors): print(paint(f"  ! {message}", "yellow", color))
        return 1
    print(paint("\n  ETA is Slurm's tentative backfill estimate and can move.", "dim", color))
    return 0

if __name__ == "__main__": raise SystemExit(main())
