#!/usr/bin/env python3
"""
gentoo_toor_selinux_bootstrap.py

Idempotent bootstrap scaffold for a Gentoo/OpenRC host that wants a
FreeBSD-style duplicate-UID-0 "toor" account, with Portage profile
inheritance, SELinux preparation, cgroups v2, and optional cgroup-device
BPF filtering.

Default mode is dry-run. Use --apply to write files and run commands.

This script intentionally does not guess your bootloader or relabel an
entire filesystem unless explicitly requested. It writes backups before
mutating existing config files.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import errno
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional


STAMP = _dt.datetime.now().strftime("%Y%m%d%H%M%S")


class Fatal(RuntimeError):
    """Fatal configuration or runtime error."""


@dataclasses.dataclass(frozen=True)
class KConfigItem:
    value: str
    tier: str
    reason: str


BASE_PACKAGES = [
    "sec-policy/selinux-base",
    "sec-policy/selinux-base-policy",
    "sec-policy/selinux-openrc",
    "sys-apps/policycoreutils",
    "sys-apps/selinux-python",
    "sys-apps/checkpolicy",
    "sys-apps/secilc",
    "app-admin/setools",
    "sys-process/audit",
]

BPF_PACKAGES = [
    "dev-util/bpftool",
    "dev-libs/libbpf",
    "sys-apps/iproute2",
]

# Required/recommended options for SELinux, cgroup v2 controllers, BPF, and
# sane setup-time diagnostics. Some symbols are architecture/filesystem
# dependent; olddefconfig will drop unavailable ones.
KCONFIG: dict[str, KConfigItem] = {
    "CONFIG_SECURITY": KConfigItem("y", "required", "LSM framework"),
    "CONFIG_SECURITYFS": KConfigItem("y", "required", "securityfs for LSMs"),
    "CONFIG_SECURITY_NETWORK": KConfigItem("y", "recommended", "network security hooks"),
    "CONFIG_SECURITY_PATH": KConfigItem("y", "recommended", "path security hooks"),
    "CONFIG_SECURITY_SELINUX": KConfigItem("y", "required", "SELinux LSM"),
    "CONFIG_SECURITY_SELINUX_BOOTPARAM": KConfigItem("y", "recommended", "selinux= boot param"),
    "CONFIG_SECURITY_SELINUX_DEVELOP": KConfigItem("y", "setup", "permissive/enforcing toggles during rollout"),
    "CONFIG_SECURITY_SELINUX_DISABLE": KConfigItem("n", "recommended", "do not allow runtime SELinux disable if symbol exists"),
    "CONFIG_AUDIT": KConfigItem("y", "required", "SELinux audit support"),
    "CONFIG_AUDITSYSCALL": KConfigItem("y", "required", "syscall audit records"),
    "CONFIG_AUDIT_TREE": KConfigItem("y", "recommended", "pathname audit support"),
    "CONFIG_NETLABEL": KConfigItem("y", "recommended", "network labeling support"),
    "CONFIG_TMPFS_XATTR": KConfigItem("y", "required", "security labels on tmpfs"),
    "CONFIG_TMPFS_POSIX_ACL": KConfigItem("y", "recommended", "ACLs on tmpfs"),
    "CONFIG_EXT4_FS_SECURITY": KConfigItem("y", "recommended", "security xattrs on ext4"),
    "CONFIG_F2FS_FS_SECURITY": KConfigItem("y", "recommended", "security xattrs on f2fs"),
    "CONFIG_JFS_SECURITY": KConfigItem("y", "recommended", "security xattrs on jfs"),
    "CONFIG_CGROUPS": KConfigItem("y", "required", "cgroup core"),
    "CONFIG_CGROUP_SCHED": KConfigItem("y", "required", "CPU controller support"),
    "CONFIG_FAIR_GROUP_SCHED": KConfigItem("y", "required", "CFS group scheduling"),
    "CONFIG_CFS_BANDWIDTH": KConfigItem("y", "recommended", "cpu.max bandwidth control"),
    "CONFIG_CGROUP_PIDS": KConfigItem("y", "required", "pids controller"),
    "CONFIG_MEMCG": KConfigItem("y", "required", "memory controller"),
    "CONFIG_BLK_CGROUP": KConfigItem("y", "required", "io controller"),
    "CONFIG_CPUSETS": KConfigItem("y", "recommended", "cpuset controller"),
    "CONFIG_CGROUP_FREEZER": KConfigItem("y", "recommended", "freeze/thaw support where available"),
    "CONFIG_BPF": KConfigItem("y", "required", "BPF core"),
    "CONFIG_BPF_SYSCALL": KConfigItem("y", "required", "bpf() syscall"),
    "CONFIG_CGROUP_BPF": KConfigItem("y", "required", "BPF programs attached to cgroups"),
    "CONFIG_BPF_JIT": KConfigItem("y", "recommended", "BPF JIT"),
    "CONFIG_BPF_JIT_ALWAYS_ON": KConfigItem("y", "recommended", "avoid BPF interpreter exposure"),
    "CONFIG_BPF_UNPRIV_DEFAULT_OFF": KConfigItem("y", "recommended", "disable unprivileged bpf by default"),
    "CONFIG_BPF_LSM": KConfigItem("y", "optional", "BPF LSM if you intentionally include bpf in lsm="),
    "CONFIG_DEBUG_INFO_BTF": KConfigItem("y", "optional", "CO-RE/BPF introspection support"),
    "CONFIG_SECURITY_LOCKDOWN_LSM": KConfigItem("y", "recommended", "kernel lockdown LSM"),
    "CONFIG_MODULE_SIG": KConfigItem("y", "recommended", "signed kernel modules"),
    "CONFIG_MODULE_SIG_ALL": KConfigItem("y", "optional", "sign all modules at build time"),
    "CONFIG_MODULE_SIG_FORCE": KConfigItem("n", "default", "do not force signatures unless explicitly requested"),
    "CONFIG_LSM": KConfigItem('"lockdown,yama,integrity,selinux"', "recommended", "default LSM order"),
}


class Runner:
    def __init__(self, apply: bool, root: Path, verbose: bool = True):
        self.apply = apply
        self.root = root.resolve()
        self.verbose = verbose

    def root_path(self, path: str | Path) -> Path:
        p = Path(path)
        if p.is_absolute():
            return self.root / str(p).lstrip("/")
        return self.root / p

    def log(self, message: str) -> None:
        print(message)

    def write_text(self, path: str | Path, content: str, mode: int = 0o644) -> None:
        target = self.root_path(path)
        self.log(f"WRITE {target} mode={mode:o}")
        if not self.apply:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
        tmp.write_text(content, encoding="utf-8", newline="\n")
        os.chmod(tmp, mode)
        os.replace(tmp, target)

    def append_unique_line(self, path: str | Path, line: str, mode: int = 0o644) -> None:
        target = self.root_path(path)
        existing = ""
        if target.exists():
            existing = target.read_text(encoding="utf-8", errors="replace")
        if line in {x.strip() for x in existing.splitlines()}:
            self.log(f"OK {target}: already contains {line!r}")
            return
        self.log(f"APPEND {target}: {line}")
        if not self.apply:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8", newline="\n") as fh:
            if existing and not existing.endswith("\n"):
                fh.write("\n")
            fh.write(line + "\n")
        os.chmod(target, mode)

    def mkdir(self, path: str | Path, mode: int = 0o755, owner: Optional[tuple[int, int]] = None) -> None:
        target = self.root_path(path)
        self.log(f"MKDIR {target} mode={mode:o}")
        if not self.apply:
            return
        target.mkdir(parents=True, exist_ok=True)
        os.chmod(target, mode)
        if owner is not None:
            os.chown(target, owner[0], owner[1])

    def chmod(self, path: str | Path, mode: int) -> None:
        target = self.root_path(path)
        self.log(f"CHMOD {target} {mode:o}")
        if self.apply:
            os.chmod(target, mode)

    def chown(self, path: str | Path, uid: int, gid: int) -> None:
        target = self.root_path(path)
        self.log(f"CHOWN {target} {uid}:{gid}")
        if self.apply:
            os.chown(target, uid, gid)

    def backup(self, path: str | Path) -> Optional[Path]:
        target = self.root_path(path)
        if not target.exists() and not target.is_symlink():
            return None
        backup = target.with_name(f"{target.name}.bak-{STAMP}")
        self.log(f"BACKUP {target} -> {backup}")
        if not self.apply:
            return backup
        if target.is_symlink():
            backup.symlink_to(os.readlink(target))
        elif target.is_dir():
            shutil.copytree(target, backup, symlinks=True)
        else:
            shutil.copy2(target, backup)
        return backup

    def symlink_force(self, target: str | Path, link: str | Path) -> None:
        link_path = self.root_path(link)
        self.log(f"SYMLINK {link_path} -> {target}")
        if not self.apply:
            return
        link_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = link_path.with_name(f".{link_path.name}.tmp-{os.getpid()}")
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        tmp.symlink_to(str(target))
        os.replace(tmp, link_path)

    def run(self, cmd: list[str], check: bool = True, capture: bool = False, chroot: bool = False) -> subprocess.CompletedProcess[str]:
        actual = cmd
        if chroot and self.root != Path("/"):
            actual = ["chroot", str(self.root)] + cmd
        self.log("RUN " + " ".join(shell_quote(x) for x in actual))
        if not self.apply:
            return subprocess.CompletedProcess(actual, 0, "", "")
        return subprocess.run(
            actual,
            check=check,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )


def shell_quote(s: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_@%+=:,./-]+", s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def read_text_if(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def command_output(cmd: list[str]) -> Optional[str]:
    try:
        cp = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return cp.stdout.strip()
    except Exception:
        return None


def detect_arch(root: Path) -> str:
    if root == Path("/") and shutil.which("portageq"):
        out = command_output(["portageq", "envvar", "ARCH"])
        if out:
            return out
    make_conf = read_text_if(root / "etc/portage/make.conf") + "\n" + read_text_if(root / "etc/make.conf")
    m = re.search(r'^\s*ARCH\s*=\s*["\']?([^"\'\s#]+)', make_conf, re.MULTILINE)
    return m.group(1) if m else "amd64"


def resolve_path_under_root(root: Path, path: Path, max_depth: int = 16) -> Path:
    """Resolve symlinks while interpreting absolute symlink targets inside root."""
    cur = path
    for _ in range(max_depth):
        if not cur.is_symlink():
            try:
                return cur.resolve(strict=False)
            except TypeError:
                return cur.resolve()
        target = os.readlink(cur)
        tpath = Path(target)
        if tpath.is_absolute():
            cur = root / str(tpath).lstrip("/")
        else:
            cur = cur.parent / tpath
    raise Fatal(f"Too many symlink indirections resolving {path}")


def display_path_from_root(root: Path, path: Path) -> str:
    """Return /-absolute display path for a path under root."""
    try:
        return "/" + path.relative_to(root).as_posix()
    except Exception:
        return str(path)


def detect_current_profile(root: Path) -> tuple[Path, str]:
    candidates = [root / "etc/portage/make.profile", root / "etc/make.profile"]
    mp = next((p for p in candidates if p.exists() or p.is_symlink()), None)
    if mp is None:
        raise Fatal("No /etc/portage/make.profile or /etc/make.profile found.")
    resolved = resolve_path_under_root(root, mp)
    # Prefer repo:path when the current profile is inside /var/db/repos/<repo>/profiles.
    repos_root = root / "var/db/repos"
    try:
        rel_to_repos = resolved.relative_to(repos_root)
        parts = rel_to_repos.parts
        if len(parts) >= 3 and parts[1] == "profiles":
            repo_dir = repos_root / parts[0]
            repo_name_file = repo_dir / "profiles/repo_name"
            repo_name = read_text_if(repo_name_file).splitlines()[0].strip() if repo_name_file.exists() else parts[0]
            profile_rel = Path(*parts[2:]).as_posix()
            return resolved, f"{repo_name}:{profile_rel}"
    except Exception:
        pass
    # Absolute parent paths are legal in cascading profiles; express them from the target root when possible.
    return resolved, display_path_from_root(root, resolved)


def profile_package_use(policy_types: list[str], include_bpf: bool) -> str:
    all_types = ["targeted", "strict", "mcs", "mls"]
    type_flags = []
    for t in all_types:
        flag = f"selinux_policy_types_{t}"
        type_flags.append(flag if t in policy_types else f"-{flag}")
    type_str = " ".join(type_flags)
    lines = [
        "# Generated by gentoo_toor_selinux_bootstrap.py",
        "# Keep OpenRC semantics and build only the selected SELinux policy types.",
        f"sec-policy/selinux-base -systemd {type_str}",
        f"sec-policy/selinux-base-policy -systemd {type_str}",
        f"sec-policy/selinux-openrc {type_str}",
        "sys-apps/policycoreutils audit pam -systemd",
        "sys-process/audit pam",
    ]
    if include_bpf:
        lines.extend([
            "sys-apps/iproute2 bpf",
        ])
    return "\n".join(lines) + "\n"


def setup_portage_profile(r: Runner, args: argparse.Namespace) -> None:
    current_profile, parent_ref = detect_current_profile(r.root)
    arch = detect_arch(r.root)
    repo_path = Path(args.repo_path)
    profile_rel = Path("profiles") / args.profile_name
    profile_path = repo_path / profile_rel

    policy_types = [x.strip() for x in args.policy_types.split(",") if x.strip()]
    invalid = sorted(set(policy_types) - {"targeted", "strict", "mcs", "mls"})
    if invalid:
        raise Fatal(f"Invalid SELinux policy type(s): {', '.join(invalid)}")

    r.log(f"Detected current profile: {current_profile}")
    r.log(f"New profile parent reference: {parent_ref}")
    r.log(f"Portage ARCH: {arch}")

    r.mkdir(repo_path / "metadata")
    r.mkdir(repo_path / "profiles")
    r.mkdir(profile_path)
    r.write_text(repo_path / "profiles/repo_name", args.repo_name + "\n")
    r.write_text(
        repo_path / "metadata/layout.conf",
        "# Generated local repository for toor/SELinux profile overlay\n"
        "masters = gentoo\n"
        "thin-manifests = true\n"
        "profile-formats = portage-2 profile-default-eapi\n"
        "profile_eapi_when_unspecified = 8\n",
    )
    r.write_text(
        repo_path / "profiles/profiles.desc",
        f"# arch profile_directory status\n{arch} {args.profile_name} exp\n",
    )
    r.write_text(profile_path / "eapi", "8\n")
    r.write_text(profile_path / "parent", parent_ref + "\n")
    r.write_text(
        profile_path / "make.defaults",
        "# Generated by gentoo_toor_selinux_bootstrap.py\n"
        "# Inherit the selected profile and add SELinux/OpenRC defaults.\n"
        "USE=\"${USE} selinux audit -systemd\"\n"
        f"SELINUX_POLICY_TYPES=\"{' '.join(policy_types)}\"\n",
    )
    package_lines = ["# Generated system-set additions for SELinux/toor posture"]
    packages = BASE_PACKAGES + (BPF_PACKAGES if args.enable_device_bpf else [])
    for pkg in packages:
        package_lines.append(f"*{pkg}")
    r.write_text(profile_path / "packages", "\n".join(package_lines) + "\n")
    r.write_text(profile_path / "package.use", profile_package_use(policy_types, args.enable_device_bpf))

    repos_conf = Path("/etc/portage/repos.conf") / f"{args.repo_name}.conf"
    r.write_text(
        repos_conf,
        f"[{args.repo_name}]\n"
        f"location = {repo_path}\n"
        "masters = gentoo\n"
        "auto-sync = no\n",
    )

    if not args.no_profile_switch:
        r.backup("/etc/portage/make.profile")
        r.symlink_force(profile_path, "/etc/portage/make.profile")


def parse_kconfig(path: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if not path.exists():
        return cfg
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, val = line.split("=", 1)
            cfg[key] = val.strip()
        else:
            m = re.fullmatch(r"# (CONFIG_[A-Za-z0-9_]+) is not set", line.strip())
            if m:
                cfg[m.group(1)] = "n"
    return cfg


def format_kconfig_value(key: str, value: str) -> str:
    if value == "n":
        return f"# {key} is not set"
    if value in {"y", "m"}:
        return f"{key}={value}"
    return f"{key}={value}"


def patch_kconfig_file(path: Path, changes: dict[str, str]) -> None:
    original = path.read_text(encoding="utf-8", errors="replace").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in original:
        key = None
        if line.startswith("CONFIG_") and "=" in line:
            key = line.split("=", 1)[0]
        else:
            m = re.fullmatch(r"# (CONFIG_[A-Za-z0-9_]+) is not set", line.strip())
            if m:
                key = m.group(1)
        if key and key in changes:
            out.append(format_kconfig_value(key, changes[key]))
            seen.add(key)
        else:
            out.append(line)
    for key in sorted(set(changes) - seen):
        out.append(format_kconfig_value(key, changes[key]))
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def setup_kernel_config(r: Runner, args: argparse.Namespace) -> None:
    cfg_path = r.root_path(args.kernel_config)
    cfg = parse_kconfig(cfg_path)
    if not cfg_path.exists():
        r.log(f"WARN kernel config not found: {cfg_path}")
        return

    desired = {k: v for k, v in KCONFIG.items() if args.include_optional_kconfig or v.tier != "optional"}
    if args.include_optional_kconfig:
        desired["CONFIG_LSM"] = KConfigItem('"lockdown,yama,integrity,selinux,bpf"', "recommended", "default LSM order with BPF LSM")
    if args.enforce_module_signing:
        desired["CONFIG_MODULE_SIG_FORCE"] = KConfigItem("y", "recommended", "enforce signed module loading")
        desired["CONFIG_MODULE_SIG_ALL"] = KConfigItem("y", "recommended", "sign all modules at build time")
    if args.lockdown == "none":
        # Still build lockdown LSM, but do not force lockdown policy at runtime.
        pass

    r.log("KCONFIG CHECK")
    missing: dict[str, str] = {}
    for key, item in sorted(desired.items()):
        have = cfg.get(key, "<absent>")
        ok = have == item.value
        mark = "OK" if ok else "SET"
        r.log(f"  {mark:3} {key:36} have={have:24} want={item.value:32} [{item.tier}] {item.reason}")
        if not ok:
            missing[key] = item.value

    if not args.patch_kconfig:
        if missing:
            r.log("Kernel .config differs. Re-run with --patch-kconfig to modify it.")
        return

    r.backup(args.kernel_config)
    r.log(f"PATCH KCONFIG {cfg_path}")
    if r.apply:
        patch_kconfig_file(cfg_path, missing)

    if args.run_olddefconfig:
        ksrc = r.root_path(args.kernel_src)
        make_cmd = ["make", "-C", str(ksrc)]
        if args.llvm:
            make_cmd.append("LLVM=1")
        make_cmd.append("olddefconfig")
        r.run(make_cmd, check=True)


def set_rc_conf_vars(content: str, assignments: dict[str, str]) -> str:
    lines = content.splitlines()
    found = set()
    out = []
    for line in lines:
        stripped = line.strip()
        replaced = False
        for key, val in assignments.items():
            if re.match(rf"^#?\s*{re.escape(key)}\s*=", stripped):
                out.append(f'{key}="{val}"')
                found.add(key)
                replaced = True
                break
        if not replaced:
            out.append(line)
    if assignments.keys() - found:
        if out and out[-1] != "":
            out.append("")
        out.append("# Added by gentoo_toor_selinux_bootstrap.py")
        for key in assignments.keys() - found:
            out.append(f'{key}="{assignments[key]}"')
    return "\n".join(out) + "\n"


def setup_openrc_cgroups(r: Runner, args: argparse.Namespace) -> None:
    rc_conf = r.root_path("/etc/rc.conf")
    current = read_text_if(rc_conf)
    updated = set_rc_conf_vars(current, {
        "rc_cgroup_mode": "unified",
        "rc_cgroup_controllers": "cpu memory io pids cpuset",
        "rc_controller_cgroups": "YES",
    })
    if updated != current:
        r.backup("/etc/rc.conf")
        r.write_text("/etc/rc.conf", updated)

    cgroup_start = f"""#!/bin/sh
# Generated by gentoo_toor_selinux_bootstrap.py
# Create a dedicated cgroup-v2 envelope for the duplicate-UID-0 toor login shell.
set -eu
CG=/sys/fs/cgroup/toor
[ -d /sys/fs/cgroup ] || exit 0
[ "$(stat -fc %T /sys/fs/cgroup 2>/dev/null || true)" = "cgroup2fs" ] || exit 0
mkdir -p "$CG"
for ctl in cpu memory io pids cpuset; do
    if grep -qw "$ctl" /sys/fs/cgroup/cgroup.controllers 2>/dev/null; then
        printf '+%s\n' "$ctl" > /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null || true
    fi
done
[ -w "$CG/memory.max" ] && printf '%s\n' '{args.toor_memory_max}' > "$CG/memory.max" || true
[ -w "$CG/memory.swap.max" ] && printf '%s\n' '{args.toor_memory_swap_max}' > "$CG/memory.swap.max" || true
[ -w "$CG/pids.max" ] && printf '%s\n' '{args.toor_pids_max}' > "$CG/pids.max" || true
[ -w "$CG/cpu.max" ] && printf '%s\n' '{args.toor_cpu_max}' > "$CG/cpu.max" || true
[ -w "$CG/io.weight" ] && printf '%s\n' '{args.toor_io_weight}' > "$CG/io.weight" || true
exit 0
"""
    r.write_text("/etc/local.d/toor-cgroup.start", cgroup_start, 0o755)

    if not args.no_cgroup_login_wrapper:
        wrapper = f"""#!/bin/bash
# Generated by gentoo_toor_selinux_bootstrap.py
# Move the toor login shell into /sys/fs/cgroup/toor, then exec bash.
set -u
CG="${{TOOR_CGROUP_PATH:-/sys/fs/cgroup/toor}}"
if [[ -d "$CG" && -w "$CG/cgroup.procs" ]]; then
    printf '%s\n' "$$" > "$CG/cgroup.procs" 2>/dev/null || true
fi
export HOME={shell_quote(args.toor_home)}
export USER=toor
export LOGNAME=toor
if [[ $# -gt 0 ]]; then
    exec {shell_quote(args.toor_shell)} "$@"
fi
exec -a "-{Path(args.toor_shell).name}" {shell_quote(args.toor_shell)} --login
"""
        r.write_text(args.toor_wrapper, wrapper, 0o755)
        r.append_unique_line("/etc/shells", args.toor_wrapper)

    if args.apply:
        if shutil.which("rc-update"):
            r.run(["rc-update", "add", "cgroups", "boot"], check=False, chroot=(r.root != Path("/")))
            r.run(["rc-update", "add", "local", "default"], check=False, chroot=(r.root != Path("/")))
            r.run(["rc-update", "add", "auditd", "default"], check=False, chroot=(r.root != Path("/")))
        else:
            r.log("WARN rc-update not found; add cgroups/local/auditd manually.")
    else:
        r.log("Would run: rc-update add cgroups boot; rc-update add local default; rc-update add auditd default")


def setup_toor_account(r: Runner, args: argparse.Namespace) -> None:
    r.mkdir(args.toor_home, 0o750, owner=(0, 0))
    shell = args.toor_wrapper if not args.no_cgroup_login_wrapper else args.toor_shell
    exists = False
    uid = None
    if r.root == Path("/"):
        try:
            ent = pwd.getpwnam("toor")
            exists = True
            uid = ent.pw_uid
        except KeyError:
            pass
    else:
        passwd_file = r.root_path("/etc/passwd")
        for line in read_text_if(passwd_file).splitlines():
            if line.startswith("toor:"):
                exists = True
                uid = int(line.split(":")[2])
                break

    if exists and uid != 0 and not args.convert_existing_toor:
        raise Fatal("User 'toor' exists but is not UID 0. Use --convert-existing-toor to modify it.")

    if exists:
        cmd = ["usermod", "--non-unique", "--uid", "0", "--gid", "0", "--home", args.toor_home, "--shell", shell, "toor"]
    else:
        cmd = [
            "useradd", "--system", "--non-unique", "--uid", "0", "--gid", "0",
            "--home-dir", args.toor_home, "--shell", shell, "--no-create-home", "toor",
        ]
    r.run(cmd, check=False, chroot=(r.root != Path("/")))

    bash_profile = f"""# Generated by gentoo_toor_selinux_bootstrap.py
export HOME={args.toor_home}
export USER=toor
export LOGNAME=toor
[ -f ~/.bashrc ] && . ~/.bashrc
"""
    bashrc = """# Generated by gentoo_toor_selinux_bootstrap.py
export HISTFILE=$HOME/.bash_history
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PS1='[\\u@\\h \\W]# '
"""
    r.write_text(Path(args.toor_home) / ".bash_profile", bash_profile, 0o644)
    r.write_text(Path(args.toor_home) / ".bashrc", bashrc, 0o644)
    r.chown(Path(args.toor_home) / ".bash_profile", 0, 0)
    r.chown(Path(args.toor_home) / ".bashrc", 0, 0)

    if args.ssh_authorized_keys:
        src = Path(args.ssh_authorized_keys)
        if not src.exists():
            raise Fatal(f"authorized_keys source not found: {src}")
        ssh_dir = Path(args.toor_home) / ".ssh"
        r.mkdir(ssh_dir, 0o700, owner=(0, 0))
        content = src.read_text(encoding="utf-8", errors="replace")
        r.write_text(ssh_dir / "authorized_keys", content, 0o600)
        r.chown(ssh_dir / "authorized_keys", 0, 0)

    r.log("NOTE: set a password manually with 'passwd toor' if password login is intended.")


def setup_selinux_files(r: Runner, args: argparse.Namespace) -> None:
    mode = args.selinux_mode
    config = f"""# Generated by gentoo_toor_selinux_bootstrap.py
SELINUX={mode}
SELINUXTYPE={args.policy_type}
"""
    r.backup("/etc/selinux/config")
    r.write_text("/etc/selinux/config", config, 0o644)


def semanage_login_map(r: Runner, args: argparse.Namespace) -> None:
    if not args.configure_selinux:
        r.log("Skipping live SELinux semanage/restorecon. Use --configure-selinux after packages and policy are installed.")
        return

    commands = ["semanage", "restorecon", "setsebool"]
    missing = [cmd for cmd in commands if r.root == Path("/") and shutil.which(cmd) is None]
    if missing:
        r.log(f"WARN missing SELinux command(s): {', '.join(missing)}. Install policycoreutils/selinux-python first.")
        return

    # Try a distinct SELinux user first; fall back to sysadm_u when the policy rejects local user creation.
    r.run(["semanage", "user", "-a", "-R", "sysadm_r", "-r", "s0-s0:c0.c1023", "toor_u"], check=False, chroot=(r.root != Path("/")))
    selinux_user = "toor_u"
    cp = r.run(["semanage", "user", "-l"], check=False, capture=True, chroot=(r.root != Path("/")))
    if r.apply and "toor_u" not in (cp.stdout or ""):
        selinux_user = "sysadm_u"
        r.log("WARN toor_u not present after semanage user add; falling back to sysadm_u")

    # Add or modify the Linux-login -> SELinux-user mapping.
    r.run(["semanage", "login", "-a", "-s", selinux_user, "-r", "s0-s0:c0.c1023", "toor"], check=False, chroot=(r.root != Path("/")))
    r.run(["semanage", "login", "-m", "-s", selinux_user, "-r", "s0-s0:c0.c1023", "toor"], check=False, chroot=(r.root != Path("/")))

    if args.enable_ssh_sysadm_login:
        r.run(["setsebool", "-P", "ssh_sysadm_login", "on"], check=False, chroot=(r.root != Path("/")))

    r.run(["semanage", "fcontext", "-a", "-e", "/root", args.toor_home], check=False, chroot=(r.root != Path("/")))
    r.run(["semanage", "fcontext", "-m", "-e", "/root", args.toor_home], check=False, chroot=(r.root != Path("/")))
    r.run(["restorecon", "-RFv", args.toor_home], check=False, chroot=(r.root != Path("/")))

    if args.schedule_relabel:
        if r.root == Path("/") and shutil.which("fixfiles"):
            r.run(["fixfiles", "-F", "onboot"], check=False)
        else:
            r.write_text("/.autorelabel", "", 0o600)


def setup_bpf_device_filter(r: Runner, args: argparse.Namespace) -> None:
    if not args.enable_device_bpf:
        return
    src = r"""// Generated by gentoo_toor_selinux_bootstrap.py
// Minimal cgroup/dev BPF filter for the /sys/fs/cgroup/toor cgroup.
#include <linux/bpf.h>
#include <linux/types.h>

#define SEC(NAME) __attribute__((section(NAME), used))

#ifndef BPF_DEVCG_ACC_MKNOD
#define BPF_DEVCG_ACC_MKNOD (1ULL << 0)
#endif
#ifndef BPF_DEVCG_ACC_READ
#define BPF_DEVCG_ACC_READ  (1ULL << 1)
#endif
#ifndef BPF_DEVCG_ACC_WRITE
#define BPF_DEVCG_ACC_WRITE (1ULL << 2)
#endif
#ifndef BPF_DEVCG_DEV_BLOCK
#define BPF_DEVCG_DEV_BLOCK (1ULL << 0)
#endif
#ifndef BPF_DEVCG_DEV_CHAR
#define BPF_DEVCG_DEV_CHAR  (1ULL << 1)
#endif

SEC("cgroup/dev")
int toor_dev_filter(struct bpf_cgroup_dev_ctx *ctx)
{
    __u32 type = ctx->access_type & 0xFFFF;

    if (type == BPF_DEVCG_DEV_CHAR) {
        // /dev/mem, /dev/kmem, /dev/port, /dev/kmsg.
        // Do not block 1:3; on Linux that is /dev/null.
        if (ctx->major == 1 &&
            (ctx->minor == 1 || ctx->minor == 2 ||
             ctx->minor == 4 || ctx->minor == 11))
            return 0;
        // /dev/kvm, usually char 10:232. Comment this out if toor manages KVM.
        if (ctx->major == 10 && ctx->minor == 232)
            return 0;
    }

    return 1;
}

char _license[] SEC("license") = "GPL";
"""
    build_script = r"""#!/bin/sh
# Generated by gentoo_toor_selinux_bootstrap.py
set -eu
SRC=/usr/local/libexec/toor-dev-filter.bpf.c
OBJ=/usr/local/libexec/toor-dev-filter.bpf.o
if [ ! -s "$OBJ" ] || [ "$SRC" -nt "$OBJ" ]; then
    clang -O2 -g -target bpf -c "$SRC" -o "$OBJ"
fi
"""
    openrc_service = r"""#!/sbin/openrc-run
# Generated by gentoo_toor_selinux_bootstrap.py
description="Attach toor cgroup-v2 device BPF filter"
command=/bin/true
CGROUP_PATH=${CGROUP_PATH:-/sys/fs/cgroup/toor}
PIN=${PIN:-/sys/fs/bpf/toor_dev_filter}
OBJ=${OBJ:-/usr/local/libexec/toor-dev-filter.bpf.o}

depend() {
    need cgroups localmount
    before sshd
}

start() {
    ebegin "Attaching toor cgroup device BPF filter"
    [ -d "$CGROUP_PATH" ] || mkdir -p "$CGROUP_PATH"
    [ -d /sys/fs/bpf ] || mkdir -p /sys/fs/bpf
    mountpoint -q /sys/fs/bpf || mount -t bpf bpf /sys/fs/bpf || return 1
    /usr/local/libexec/toor-build-dev-filter
    if ! bpftool prog show pinned "$PIN" >/dev/null 2>&1; then
        rm -f "$PIN"
        bpftool prog load "$OBJ" "$PIN" type cgroup/dev || return 1
    fi
    bpftool cgroup attach "$CGROUP_PATH" device pinned "$PIN" 2>/dev/null || true
    eend 0
}
"""
    r.mkdir("/usr/local/libexec", 0o755)
    r.write_text("/usr/local/libexec/toor-dev-filter.bpf.c", src, 0o644)
    r.write_text("/usr/local/libexec/toor-build-dev-filter", build_script, 0o755)
    r.write_text("/etc/init.d/toor-bpf-devfilter", openrc_service, 0o755)
    if args.apply and shutil.which("rc-update"):
        r.run(["rc-update", "add", "toor-bpf-devfilter", "default"], check=False, chroot=(r.root != Path("/")))
    else:
        r.log("Would run: rc-update add toor-bpf-devfilter default")


def setup_boot_cmdline(r: Runner, args: argparse.Namespace) -> None:
    tokens = [
        "audit=1",
        "selinux=1",
        "enforcing=1" if args.selinux_mode == "enforcing" else "enforcing=0",
        "lsm=lockdown,yama,integrity,selinux" + (",bpf" if args.include_optional_kconfig else ""),
    ]
    if args.cgroup_no_v1:
        tokens.append("cgroup_no_v1=all")
    if args.lockdown != "none":
        tokens.append(f"lockdown={args.lockdown}")
        if args.enable_device_bpf:
            r.log("WARN: lockdown may restrict BPF loading. Attach cgroup BPF before lockdown enforcement or test this path carefully.")

    cmdline = " ".join(tokens)
    r.write_text("/etc/kernel/cmdline.toor-selinux", cmdline + "\n", 0o644)

    if not args.update_grub:
        r.log(f"Kernel command line fragment written/planned: {cmdline}")
        r.log("Use --update-grub to patch /etc/default/grub automatically.")
        return

    grub = r.root_path("/etc/default/grub")
    if not grub.exists():
        r.log("WARN /etc/default/grub not found; not patching bootloader config.")
        return
    current = read_text_if(grub)
    pattern = re.compile(r'^(GRUB_CMDLINE_LINUX(?:_DEFAULT)?=)(["\'])(.*)(["\'])$', re.MULTILINE)
    key_seen = False

    def repl(m: re.Match[str]) -> str:
        nonlocal key_seen
        key_seen = True
        existing = m.group(3).split()
        merged = existing[:]
        existing_keys = {x.split("=", 1)[0] for x in existing}
        for token in tokens:
            k = token.split("=", 1)[0]
            if k not in existing_keys:
                merged.append(token)
        return f"{m.group(1)}{m.group(2)}{' '.join(merged)}{m.group(4)}"

    updated = pattern.sub(repl, current)
    if not key_seen:
        updated += f'\nGRUB_CMDLINE_LINUX="{cmdline}"\n'
    if updated != current:
        r.backup("/etc/default/grub")
        r.write_text("/etc/default/grub", updated, 0o644)
    if args.run_grub_mkconfig:
        out = args.grub_cfg
        r.run(["grub-mkconfig", "-o", out], check=False, chroot=(r.root != Path("/")))


def maybe_emerge(r: Runner, args: argparse.Namespace) -> None:
    packages = BASE_PACKAGES + (BPF_PACKAGES if args.enable_device_bpf else [])
    cmd = ["emerge", "--ask", "--verbose", "--changed-use", "--deep"] + packages
    if args.emerge:
        r.run(cmd, check=True, chroot=(r.root != Path("/")))
        r.run(["emerge", "--ask", "--verbose", "--changed-use", "--deep", "--newuse", "@world"], check=False, chroot=(r.root != Path("/")))
    else:
        r.log("Install/update command not executed. Suggested:")
        r.log("  " + " ".join(shell_quote(x) for x in cmd))
        r.log("  emerge --ask --verbose --changed-use --deep --newuse @world")


def verify_runtime(r: Runner) -> None:
    r.log("Runtime verification commands after reboot:")
    checks = [
        "id toor",
        "id -Z",
        "getenforce || true",
        "sestatus || true",
        "stat -fc %T /sys/fs/cgroup",
        "cat /sys/fs/cgroup/cgroup.controllers",
        "cat /proc/$$/cgroup",
        "semanage login -l | grep -E '^(toor|root|__default__)' || true",
        "ps -o pid,user,euser,label,cmd -p $$",
    ]
    for c in checks:
        r.log("  " + c)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Bootstrap Gentoo/OpenRC duplicate-UID-0 toor + SELinux + cgroup-v2 posture.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--apply", action="store_true", help="write files and run commands; default is dry-run")
    p.add_argument("--root", default="/", help="target root/chroot path")
    p.add_argument("--repo-name", default="local-toor-selinux", help="local Portage repository name")
    p.add_argument("--repo-path", default="/var/db/repos/local-toor-selinux", help="local Portage repository path")
    p.add_argument("--profile-name", default="toor-selinux-llvm", help="local profile directory name")
    p.add_argument("--no-profile-switch", action="store_true", help="create profile but do not repoint /etc/portage/make.profile")
    p.add_argument("--policy-type", default="targeted", choices=["targeted", "strict", "mcs", "mls"], help="SELinux runtime policy type")
    p.add_argument("--policy-types", default="targeted", help="comma-separated SELinux policy types to build via Portage USE_EXPAND")
    p.add_argument("--selinux-mode", default="permissive", choices=["permissive", "enforcing", "disabled"], help="/etc/selinux/config mode")
    p.add_argument("--emerge", action="store_true", help="run emerge for SELinux/BPF packages")
    p.add_argument("--configure-selinux", action="store_true", help="run semanage/restorecon/setsebool live operations")
    p.add_argument("--enable-ssh-sysadm-login", action="store_true", help="set ssh_sysadm_login boolean for sysadm_t SSH login")
    p.add_argument("--schedule-relabel", action="store_true", help="schedule full filesystem relabel on next boot")
    p.add_argument("--toor-home", default="/toor", help="toor home directory")
    p.add_argument("--toor-shell", default="/bin/bash", help="real shell to exec for toor")
    p.add_argument("--toor-wrapper", default="/usr/local/sbin/toor-login-shell", help="login-shell wrapper used to enter cgroup")
    p.add_argument("--no-cgroup-login-wrapper", action="store_true", help="leave toor shell as --toor-shell instead of wrapper")
    p.add_argument("--convert-existing-toor", action="store_true", help="convert existing toor account to UID/GID 0")
    p.add_argument("--ssh-authorized-keys", help="path to authorized_keys to install into /toor/.ssh")
    p.add_argument("--kernel-src", default="/usr/src/linux", help="kernel source tree")
    p.add_argument("--kernel-config", default="/usr/src/linux/.config", help="kernel .config to check/patch")
    p.add_argument("--patch-kconfig", action="store_true", help="patch kernel .config values")
    p.add_argument("--include-optional-kconfig", action="store_true", help="also check/patch optional BPF/BTF/module-signing niceties")
    p.add_argument("--run-olddefconfig", action="store_true", help="run make olddefconfig after patching .config")
    p.add_argument("--llvm", action=argparse.BooleanOptionalAction, default=True, help="pass LLVM=1 to make olddefconfig")
    p.add_argument("--enforce-module-signing", action="store_true", help="set CONFIG_MODULE_SIG_FORCE=y")
    p.add_argument("--lockdown", default="none", choices=["none", "integrity", "confidentiality"], help="kernel lockdown mode to add to cmdline")
    p.add_argument("--cgroup-no-v1", action=argparse.BooleanOptionalAction, default=True, help="add cgroup_no_v1=all to cmdline")
    p.add_argument("--toor-memory-max", default="max", help="cgroup memory.max")
    p.add_argument("--toor-memory-swap-max", default="max", help="cgroup memory.swap.max")
    p.add_argument("--toor-pids-max", default="8192", help="cgroup pids.max")
    p.add_argument("--toor-cpu-max", default="max", help="cgroup cpu.max, e.g. '400000 100000'")
    p.add_argument("--toor-io-weight", default="100", help="cgroup io.weight")
    p.add_argument("--enable-device-bpf", action="store_true", help="generate and enable optional cgroup/dev BPF filter")
    p.add_argument("--update-grub", action="store_true", help="patch /etc/default/grub with kernel cmdline tokens")
    p.add_argument("--run-grub-mkconfig", action="store_true", help="run grub-mkconfig after patching /etc/default/grub")
    p.add_argument("--grub-cfg", default="/boot/grub/grub.cfg", help="grub-mkconfig output path")
    p.add_argument("--skip-portage", action="store_true", help="skip local Portage profile/repo setup")
    p.add_argument("--skip-kernel", action="store_true", help="skip kernel .config checks")
    p.add_argument("--skip-openrc", action="store_true", help="skip OpenRC cgroup/local.d setup")
    p.add_argument("--skip-account", action="store_true", help="skip toor account setup")
    p.add_argument("--skip-selinux-files", action="store_true", help="skip /etc/selinux/config write")
    p.add_argument("--skip-cmdline", action="store_true", help="skip kernel command-line fragment/GRUB patch")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.root).resolve()
    r = Runner(apply=args.apply, root=root)

    if args.apply and root == Path("/") and os.geteuid() != 0:
        raise Fatal("--apply requires root privileges.")

    if args.selinux_mode == "disabled":
        r.log("WARN: SELINUX=disabled defeats the SELinux confinement objective; use only for rollback.")

    if not args.skip_portage:
        setup_portage_profile(r, args)
    if not args.skip_kernel:
        setup_kernel_config(r, args)
    if not args.skip_openrc:
        setup_openrc_cgroups(r, args)
    if not args.skip_account:
        setup_toor_account(r, args)
    if not args.skip_selinux_files:
        setup_selinux_files(r, args)
    if args.enable_device_bpf:
        setup_bpf_device_filter(r, args)
    if not args.skip_cmdline:
        setup_boot_cmdline(r, args)
    maybe_emerge(r, args)
    semanage_login_map(r, args)
    verify_runtime(r)

    r.log("Done. Default SELinux rollout path is permissive first, relabel, verify AVCs, then enforcing.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Fatal as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(2)
