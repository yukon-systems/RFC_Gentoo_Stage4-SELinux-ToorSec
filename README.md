## RFC1918's Gentoo Stage4 + SELinux on LLVM/Clang

OS: Gentoo 
Init: OpenRC
Super: `toor` Superuser Enablement
Stage4+: SELinux, cgroups v2, BPF
Config: Portage Sub-Profile Control


### Templates and Other Fun
This repo was created via Yukon's standard-defs template repo, and therefore includes defaults which can be found in the `.github` and `structs` directories.

```text
.github/ISSUE_TEMPLATE/
.github/PULL_REQUEST_TEMPLATE/
structs/opersys/git/
```

### **Operator Notes**
- Start with `structs/opersys/git/github-templates-compliance.md` when adapting these standards into another YukonSYS repository.
- Meat&Potatoes follow below..

---

### Superuser Enablement with SELinux, cgroups v2, BPF, and Portage Sub-Profile Control

**Target platform:** Gentoo Linux, `amd64`, OpenRC, LLVM/Clang kernel build path, no systemd dependency
**Target kernel families:** Linux `6.18.x` longterm and Linux `7.x` stable/current
**Generated:** 2026-05-28 America/Los_Angeles
**Companion script:** `gentoo_toor_selinux_bootstrap.py`

---

## 1. Introduction

This document describes a Gentoo-specific implementation pattern for a FreeBSD-style alternate superuser account named `toor`:

```bash
useradd --system --non-unique --uid 0 --gid 0 --home-dir /toor --shell /bin/bash --no-create-home toor
```

The operational goal is explicit:

```text
A direct login as toor starts with uid=0/euid=0 and does not require sudo, doas, pfexec, su, or another prefix/elevation command.
```

On Linux, that goal is achieved at the POSIX credential layer by assigning UID `0` to `toor`. The security problem is that POSIX DAC, file ownership, and many legacy audit/accounting paths collapse all UID `0` identities into the same kernel credential. The compensating design in this document is therefore:

```text
duplicate UID 0 account
+ separate home directory
+ SELinux login mapping and role/domain labeling
+ OpenRC-managed cgroup v2 resource envelope
+ optional cgroup-device BPF filter
+ kernel lockdown/module-signing/audit controls
+ Portage profile encapsulation for repeatability
```

The companion script implements this as a **local Portage sub-profile** that inherits the current system profile through a `parent` entry, then adds SELinux/OpenRC/cgroup/kernel/account configuration around it. Portage cascading profiles support `parent` inheritance and ordered parent processing, so this approach avoids editing the Gentoo repository profile in place.[^portage-profile]

The recommended security target is not merely:

```text
toor:x:0:0::/toor:/bin/bash
```

The recommended target is closer to:

```text
toor:x:0:0::/toor:/usr/local/sbin/toor-login-shell
SELinux context: toor_u:sysadm_r:sysadm_t:s0-s0:c0.c1023
cgroup path: /sys/fs/cgroup/toor
boot: audit=1 selinux=1 cgroup_no_v1=all lsm=lockdown,yama,integrity,selinux
```

---

## 2. Problem description

### 2.1 Native Linux root equivalence

For the behavior requested, the decisive state is:

```text
uid=0
euid=0
```

A user in `wheel`, `sudo`, or another admin group is not intrinsically root-equivalent to the kernel. Such groups only matter when userland policy checks them. Direct no-prefix root-equivalence requires the process to start as UID `0`, or to acquire effective UID `0` through some transition mechanism. Since the design intentionally avoids prefix transitions such as `sudo`, the login account itself must be UID `0`.

### 2.2 Risks introduced by duplicate UID `0`

A duplicate UID `0` account provides the desired workflow but creates several structural issues.

| Concern | Why it exists | Whether this design eliminates it |
|---|---|---:|
| POSIX ownership ambiguity | Files owned by UID `0` may render as `root` or `toor` depending on NSS/passwd lookup order. | No |
| DAC equivalence | POSIX DAC sees both accounts as UID `0`. | No |
| Process/user rendering ambiguity | Tools such as `ps`, `id -un`, `whoami`, and `ls -l` are often UID-name renderers, not separate identity systems. | No |
| Audit collapse on UID fields | UID/AUID/EUID fields alone cannot reliably distinguish `root` from `toor`. | Partially mitigated by SELinux subject context |
| Full system compromise if unconfined | UID `0` with `unconfined_t` is effectively just root. | Yes, if SELinux is enforcing and `toor` is confined |
| Resource exhaustion | Root can consume CPU, memory, process IDs, and I/O. | Partially mitigated by cgroups v2 |
| Direct device/kernel attack surface | UID `0` can reach dangerous device nodes and kernel interfaces unless separately constrained. | Partially mitigated by SELinux, lockdown, module signing, and cgroup-device BPF |

### 2.3 Desired compensating controls

The design uses multiple layers because each solves a different part of the problem:

| Layer | Primary purpose | Important limitation |
|---|---|---|
| SELinux | Mandatory access control and audit distinction by context, independent of UID. | Only useful if enforcing or selectively permissive during rollout. |
| cgroups v2 | Resource and device-access envelope. | Not an identity model. Root can often alter cgroups unless MAC/lockdown prevents it. |
| cgroup-device BPF | Deny selected device access under a cgroup. | Requires BPF tooling and careful lockdown interaction testing. |
| Kernel lockdown | Reduces root's ability to modify/read kernel memory and use sensitive kernel interfaces. | Can interfere with BPF, kprobes, debug workflows, and unsigned module workflows. |
| Module signing | Prevents or flags unsigned/untrusted kernel module loading. | Requires a mature key-management workflow before enforcing signatures. |
| Audit | Captures SELinux denials, login/session data, and kernel security events. | Does not fix UID collapse by itself. |
| Portage sub-profile | Makes the posture reproducible and testable across systems. | Does not replace runtime validation. |

---

## 3. Comparison to FreeBSD method of solution

FreeBSD has the cleanest historical version of this pattern. Its FAQ describes `toor` as an alternate superuser account with UID `0`, intended for use with a non-standard shell so the primary `root` shell can remain conservative and recoverable.[^freebsd-toor]

### 3.1 FreeBSD model

Typical FreeBSD intent:

```text
root  -> UID 0, conservative base-system shell, recovery-safe
toor  -> UID 0, alternate shell or alternate admin login context
```

The account exists in the base account model. The administrator enables it by setting a password or another authentication method, then assigns the desired shell and operational controls.

### 3.2 Linux/Gentoo equivalent

Linux does not normally ship a `toor` account. The Gentoo implementation therefore creates the account and then adds MAC/resource controls:

```text
root  -> UID 0, break-glass, optionally unconfined
toor  -> UID 0, direct admin login, SELinux-mapped and cgroup-wrapped
```

### 3.3 Key differences

| Dimension | FreeBSD `toor` | Gentoo/Linux `toor` design |
|---|---|---|
| Account availability | Traditionally present or documented as a built-in alternate superuser account. | Must be created locally. |
| Kernel primitive | UID `0`. | UID `0`. |
| Distinction layer | Login name, shell, home, and BSD account database conventions. | Login name, shell, home, SELinux context, audit label, cgroup placement. |
| Primary security caveat | Duplicate UID `0` still collapses identity at the UID layer. | Same caveat, but SELinux can add a MAC identity layer. |
| Best operational use | Alternate shell/recovery account. | Direct admin account with mandatory-access-control hardening. |

The Linux implementation is less native than FreeBSD's, but with SELinux it can gain a distinction layer FreeBSD's plain `toor` mechanism does not inherently provide.

---

## 4. Comparison to Solaris method of solution

Solaris 11.x approaches this differently. Solaris has a mature RBAC model where `root` may be a role rather than a directly logged-in user. Oracle documents changing `root` from a role into a normal user with:

```sh
rolemod -K type=normal root
```

That procedure is specifically for systems where `root` must be able to log in directly.[^solaris-root-role]

### 4.1 Solaris model

Solaris security architecture centers on:

```text
users
roles
rights profiles
privileges
authorizations
```

This model tries to avoid the all-or-nothing semantics of persistent UID `0` sessions. Administrators log in as themselves and assume roles or use rights profiles.

### 4.2 Linux approximation

The closest Linux approximation is not cgroups. It is SELinux:

```text
Linux login name -> SELinux user -> SELinux role -> SELinux domain/type
```

The script's default SELinux direction is:

```text
toor -> toor_u -> sysadm_r -> sysadm_t
```

or, if `toor_u` cannot be created under the installed policy:

```text
toor -> sysadm_u -> sysadm_r -> sysadm_t
```

The `semanage` user/login mechanism is the right tool for this mapping; `semanage login` maps Linux login names to SELinux users, while `semanage user` maps SELinux users to authorized roles and ranges.[^semanage]

### 4.3 Key differences

| Dimension | Solaris 11.x | Gentoo/Linux design |
|---|---|---|
| Preferred admin model | RBAC roles and rights profiles. | POSIX UID `0` plus SELinux MAC. |
| Direct root login | Possible by converting `root` from role to normal user. | Possible by duplicate UID `0` account. |
| No-prefix admin workflow | Direct root user or UID `0` account. | Direct UID `0` account. |
| Fine-grained privilege model | Solaris privileges and rights profiles. | SELinux domains, Linux capabilities, kernel lockdown, cgroups. |
| Best compliance posture | Keep RBAC unless direct root login is explicitly required. | Keep SELinux enforcing and avoid `unconfined_t` for `toor`. |

Solaris is more structurally mature for role-based administration. Linux can approximate the separation with SELinux, but the design remains less elegant if the account must literally be UID `0` from login.

---

## 5. Linux kernel config matrix: 6.18.x vs 7.x

As of this writing, kernel.org lists Linux `6.18.33` as a longterm kernel and Linux `7.0.10` as the stable kernel, both dated 2026-05-23.[^kernel-org] The matrix below treats `6.18.x` and `7.x` as requiring the same security posture. The practical difference is release governance: `6.18.x` is the better conservative baseline for fleet rollout, while `7.x` is the better early-integration track for catching upcoming behavior changes.

The script checks and optionally patches the kernel `.config`, then can run:

```bash
make -C /usr/src/linux LLVM=1 olddefconfig
```

`olddefconfig` remains essential because symbol availability and dependencies can differ by architecture, selected filesystems, selected LSMs, and kernel branch.

### 5.1 Matrix

| Area | Kernel config / boot setting | 6.18.x recommendation | 7.x recommendation | Purpose / validation |
|---|---|---:|---:|---|
| LSM core | `CONFIG_SECURITY=y` | Required | Required | Enables the Linux Security Module framework. |
| LSM core | `CONFIG_SECURITYFS=y` | Required | Required | Required for `/sys/kernel/security` and runtime LSM inspection. |
| LSM ordering | `CONFIG_LSM="lockdown,yama,integrity,selinux"` | Recommended | Recommended | Provides default LSM order; verify with `/sys/kernel/security/lsm`. |
| LSM ordering with BPF LSM | `CONFIG_LSM="lockdown,yama,integrity,selinux,bpf"` | Optional | Optional | Only when intentionally using BPF LSM in addition to cgroup BPF. |
| SELinux | `CONFIG_SECURITY_SELINUX=y` | Required | Required | Builds SELinux as the major MAC LSM. |
| SELinux boot params | `CONFIG_SECURITY_SELINUX_BOOTPARAM=y` | Recommended | Recommended | Allows `selinux=` boot-time control during rollout. |
| SELinux development toggles | `CONFIG_SECURITY_SELINUX_DEVELOP=y` | Setup phase | Setup phase | Allows permissive/enforcing transitions during migration. |
| Runtime SELinux disable | `CONFIG_SECURITY_SELINUX_DISABLE=n` | Recommended | Recommended | Avoids runtime disable path where the symbol exists. |
| SELinux network hooks | `CONFIG_SECURITY_NETWORK=y` | Recommended | Recommended | Needed for full network object mediation. |
| SELinux path hooks | `CONFIG_SECURITY_PATH=y` | Recommended | Recommended | Useful for path-mediated hooks and policy coverage. |
| Audit | `CONFIG_AUDIT=y` | Required | Required | SELinux audit and AVC visibility. |
| Audit syscall | `CONFIG_AUDITSYSCALL=y` | Required | Required | Syscall-level audit records. |
| Audit path tree | `CONFIG_AUDIT_TREE=y` | Recommended | Recommended | Richer pathname audit support. |
| Network labeling | `CONFIG_NETLABEL=y` | Recommended | Recommended | Required for labeled networking cases. |
| tmpfs labels | `CONFIG_TMPFS_XATTR=y` | Required | Required | Allows security labels on tmpfs. |
| tmpfs ACL | `CONFIG_TMPFS_POSIX_ACL=y` | Recommended | Recommended | Preserves expected POSIX ACL behavior on tmpfs. |
| ext4 labels | `CONFIG_EXT4_FS_SECURITY=y` | Recommended if ext4 | Recommended if ext4 | Security xattrs on ext4. |
| f2fs labels | `CONFIG_F2FS_FS_SECURITY=y` | Recommended if f2fs | Recommended if f2fs | Security xattrs on f2fs. |
| jfs labels | `CONFIG_JFS_SECURITY=y` | Recommended if jfs | Recommended if jfs | Security xattrs on jfs. |
| cgroup core | `CONFIG_CGROUPS=y` | Required | Required | cgroup v2 hierarchy support. |
| CPU controller | `CONFIG_CGROUP_SCHED=y` | Required | Required | CPU resource controller infrastructure. |
| CFS group scheduling | `CONFIG_FAIR_GROUP_SCHED=y` | Required | Required | Required for CPU group scheduling. |
| CPU bandwidth | `CONFIG_CFS_BANDWIDTH=y` | Recommended | Recommended | Supports `cpu.max`. |
| PID controller | `CONFIG_CGROUP_PIDS=y` | Required | Required | Supports `pids.max`. |
| Memory controller | `CONFIG_MEMCG=y` | Required | Required | Supports `memory.max` and related memory accounting. |
| I/O controller | `CONFIG_BLK_CGROUP=y` | Required | Required | Supports block I/O control paths used by cgroup v2 I/O controller. |
| cpuset | `CONFIG_CPUSETS=y` | Recommended | Recommended | Supports cpuset placement where needed. |
| freezer | `CONFIG_CGROUP_FREEZER=y` | Recommended where available | Recommended where available | Freeze/thaw support for managed cgroups. |
| BPF core | `CONFIG_BPF=y` | Required for device BPF | Required for device BPF | BPF core. |
| BPF syscall | `CONFIG_BPF_SYSCALL=y` | Required for device BPF | Required for device BPF | Allows BPF program load/attach tooling. |
| cgroup BPF | `CONFIG_CGROUP_BPF=y` | Required for device BPF | Required for device BPF | Required for cgroup-attached BPF programs. |
| BPF JIT | `CONFIG_BPF_JIT=y` | Recommended | Recommended | Performance and normal production BPF posture. |
| BPF JIT always on | `CONFIG_BPF_JIT_ALWAYS_ON=y` | Recommended | Recommended | Avoids interpreter exposure where acceptable. |
| Unprivileged BPF | `CONFIG_BPF_UNPRIV_DEFAULT_OFF=y` | Recommended | Recommended | Disables unprivileged BPF by default. |
| BPF LSM | `CONFIG_BPF_LSM=y` | Optional | Optional | Only if intentionally adding `bpf` to LSM order. |
| BTF debug info | `CONFIG_DEBUG_INFO_BTF=y` | Optional | Optional | Useful for CO-RE/BPF observability and tooling. |
| Lockdown | `CONFIG_SECURITY_LOCKDOWN_LSM=y` | Recommended | Recommended | Enables kernel lockdown LSM. |
| Module signing | `CONFIG_MODULE_SIG=y` | Recommended | Recommended | Supports signed kernel modules. |
| Sign all modules | `CONFIG_MODULE_SIG_ALL=y` | Optional | Optional | Useful when module signing workflow is ready. |
| Enforce signed modules | `CONFIG_MODULE_SIG_FORCE=y` | Only after key workflow is mature | Only after key workflow is mature | Rejects unsigned/untrusted modules. |
| Unified cgroup boot | `cgroup_no_v1=all` | Recommended | Recommended | Forces no legacy cgroup v1 controllers where compatible. |
| SELinux boot | `selinux=1 enforcing=0` initially | Recommended for first boot | Recommended for first boot | Boot permissive first, relabel, then enforce. |
| Audit boot | `audit=1` | Recommended | Recommended | Ensures audit capture early in boot. |
| Lockdown boot | `lockdown=integrity` | Optional after testing | Optional after testing | Can restrict BPF/debug paths; test with device filter. |

### 5.2 cgroup v2 and BPF-specific notes

The Linux cgroup v2 device controller has no traditional interface files; it is implemented on top of cgroup BPF. Device access can be permitted or denied by `BPF_PROG_TYPE_CGROUP_DEVICE` programs attached with `BPF_CGROUP_DEVICE`.[^cgroup-v2-device]

That matters because the script's optional BPF device filter is not a cgroup-v1 device whitelist. It is a cgroup-device BPF program that denies selected high-risk character devices such as:

```text
/dev/mem
/dev/kmem
/dev/port
/dev/kmsg
/dev/kvm
```

### 5.3 Lockdown and module-signing notes

Kernel lockdown is designed to prevent direct and indirect access to the running kernel image and restrict interfaces such as `/dev/mem`, `/dev/kmem`, `/dev/kcore`, BPF, kprobes, debugfs, and unsigned module loading paths.[^kernel-lockdown]

Module signing cryptographically signs modules and checks signatures on load. `CONFIG_MODULE_SIG_FORCE=y` makes unsigned or untrusted modules fail to load, while leaving it off permits unsigned modules but taints the kernel.[^module-signing]

Operational recommendation:

```text
Phase 1: CONFIG_MODULE_SIG=y, CONFIG_MODULE_SIG_FORCE=n
Phase 2: sign all in-tree and out-of-tree modules reproducibly
Phase 3: test boot, initramfs, GPU/NIC/HBA modules, and rescue media
Phase 4: enable CONFIG_MODULE_SIG_FORCE=y or module.sig_enforce=1
```

---

## 6. Decision optimization for SELinux type: targeted, MLS, MCS/“MLC”

Gentoo's `sec-policy/selinux-base-policy` exposes SELinux policy USE_EXPAND values for `mcs`, `mls`, `strict`, and `targeted`.[^gentoo-selinux-base-policy] The user-provided term `mlc` is treated here as likely referring to **MCS**, Multi-Category Security. `mlc` is not a Gentoo SELinux policy type exposed by the package metadata.

### 6.1 Type selection table

| SELinux policy type | Best fit | Advantages | Costs | Recommendation for `toor` posture |
|---|---|---|---|---|
| `targeted` | General-purpose Gentoo host, admin node, build host, HPC login/build infrastructure. | Lowest migration friction; broadest policy maturity; supports confined services while allowing practical operations. | Less strict than full strict/MLS designs; unconfined policy modules can dilute posture if enabled broadly. | **Default recommendation.** Start here. |
| `mcs` | Category-based separation where processes/data need category labels but not formal sensitivity levels. | Useful stepping stone for multi-tenant or workload category isolation. | More label/range management; not needed for a simple `toor` admin identity. | Build as secondary policy type if future category isolation is likely. |
| `mls` | Formal multi-level security with sensitivity levels and clearances. | Strong confidentiality model for classified or compartmentalized data. | High operational complexity; MLS rules combine with DAC, and higher clearance does not imply admin rights.[^selinux-mls] | Use only if the environment actually requires MLS semantics. |
| `strict` | Maximum SELinux coverage for local users and services. | Stronger confinement model. | Higher migration burden; more local policy work. | Consider after `targeted` is stable, not first rollout. |

### 6.2 Practical recommendation

For the described Gentoo/OpenRC/HPC/buildroot workflow:

```text
Runtime policy type: targeted
Built policy types: targeted initially; targeted,mcs if future category isolation is likely
Avoid initial MLS unless a formal MLS requirement already exists
```

Script defaults:

```bash
--policy-type targeted
--policy-types targeted
```

Optional future-proofing:

```bash
--policy-type targeted --policy-types targeted,mcs
```

MLS should be treated as a separate program, not a flag flip. The Red Hat MLS documentation explicitly warns that MLS rules are combined with conventional DAC and that higher clearance does not automatically grant administrative rights; it also warns against MLS on systems running X Window System.[^selinux-mls]

---

## 7. Decision optimization for SELinux mode: enforcing, permissive, permissive domains

### 7.1 Mode selection table

| Mode | Meaning | Best use | Risk | Recommendation |
|---|---|---|---|---|
| `permissive` | SELinux logs would-be denials but does not enforce them globally. | Initial migration, first boot after relabel, policy discovery. | No meaningful protection from SELinux while global permissive. | Use only during staged rollout. |
| `enforcing` | SELinux denies policy violations. | Final production posture. | Mislabeling or missing policy can break services or login flows. | Required final state. |
| permissive domains | Global enforcing remains active, but selected domains log instead of deny. | Debugging one domain while keeping the rest of the host protected. | Dangerous if the permissive domain is broad, such as shared `sysadm_t`. | Use with a custom `toor_t` domain, not shared `sysadm_t`, if possible. |

The SELinux Project documentation describes `semanage permissive` as the command that adds or removes a policy module setting a requested domain into permissive mode.[^selinux-project-permissive] Red Hat's SELinux guidance frames this as preferable to making the whole system permissive: one domain can be permissive while other domains remain enforcing.[^redhat-permissive-domain]

### 7.2 Recommended mode progression

```text
Stage A: SELINUX=permissive, SELINUXTYPE=targeted
Stage B: relabel filesystem
Stage C: verify toor login context and service behavior
Stage D: global enforcing
Stage E: optional per-domain permissive only for custom toor_t if needed
Stage F: remove permissive domains after policy is fixed
```

### 7.3 Commands

Global permissive:

```bash
setenforce 0
sed -i 's/^SELINUX=.*/SELINUX=permissive/' /etc/selinux/config
```

Global enforcing:

```bash
setenforce 1
sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
```

Per-domain permissive, after creating a custom domain:

```bash
semanage permissive -a toor_t
semanage permissive -l
```

Return a domain to enforcing:

```bash
semanage permissive -d toor_t
```

Avoid this unless you intentionally want every `sysadm_t` session permissive:

```bash
semanage permissive -a sysadm_t
```

---

## 8. Solutions offered by the script

The script is a bootstrap scaffold. It is dry-run by default and mutates the target only when `--apply` is supplied.

### 8.1 Portage sub-profile

Creates a local repository and sub-profile:

```text
/var/db/repos/local-toor-selinux/
  metadata/layout.conf
  profiles/repo_name
  profiles/profiles.desc
  profiles/toor-selinux-llvm/
    eapi
    parent
    make.defaults
    packages
    package.use
```

It then optionally repoints:

```text
/etc/portage/make.profile -> /var/db/repos/local-toor-selinux/profiles/toor-selinux-llvm
```

The generated profile inherits the current profile through the `parent` file, adds `selinux audit -systemd` to USE defaults, adds SELinux packages to the system set through profile `packages`, and sets SELinux policy type USE_EXPAND values in `package.use`.

### 8.2 Package enablement

Base packages added by the script:

```text
sec-policy/selinux-base
sec-policy/selinux-base-policy
sec-policy/selinux-openrc
sys-apps/policycoreutils
sys-apps/selinux-python
sys-apps/checkpolicy
sys-apps/secilc
app-admin/setools
sys-process/audit
```

Optional BPF packages:

```text
dev-util/bpftool
dev-libs/libbpf
sys-apps/iproute2
```

Gentoo's `sys-apps/selinux-python` package provides SELinux Python utilities including `semanage`, `sepolicy`, and `sepolgen`.[^gentoo-selinux-python] Gentoo's `sec-policy/selinux-openrc` package provides SELinux policy for OpenRC and exposes the same policy type flags.[^gentoo-selinux-openrc]

### 8.3 Kernel config checking and patching

The script checks the running tree or target `.config` for the symbols listed in the matrix. With `--patch-kconfig`, it modifies the `.config`. With `--run-olddefconfig`, it runs:

```bash
make -C /usr/src/linux LLVM=1 olddefconfig
```

The script deliberately does not build or install the kernel, because Gentoo kernel workflows vary.

### 8.4 `toor` account creation

Creates `/toor`, then creates or modifies `toor` as UID/GID `0`:

```bash
useradd --system --non-unique --uid 0 --gid 0 \
  --home-dir /toor \
  --shell /usr/local/sbin/toor-login-shell \
  --no-create-home \
  toor
```

The wrapper shell moves the login shell into `/sys/fs/cgroup/toor` before execing the real shell.

### 8.5 SELinux files and live SELinux setup

Writes:

```text
/etc/selinux/config
```

Example:

```text
SELINUX=permissive
SELINUXTYPE=targeted
```

When `--configure-selinux` is supplied after SELinux userspace is installed, the script attempts:

```bash
semanage user -a -R sysadm_r -r s0-s0:c0.c1023 toor_u
semanage login -a -s toor_u -r s0-s0:c0.c1023 toor
setsebool -P ssh_sysadm_login on
semanage fcontext -a -e /root /toor
restorecon -RFv /toor
```

If `toor_u` cannot be created, it falls back to `sysadm_u`.

### 8.6 OpenRC cgroup v2

Updates `/etc/rc.conf` with:

```text
rc_cgroup_mode="unified"
rc_cgroup_controllers="cpu memory io pids cpuset"
rc_controller_cgroups="YES"
```

OpenRC's own `rc.conf` comments define `unified` as mounting cgroup v2 on `/sys/fs/cgroup`.[^openrc-cgroup]

The script also writes:

```text
/etc/local.d/toor-cgroup.start
/usr/local/sbin/toor-login-shell
```

and enables OpenRC services when possible:

```bash
rc-update add cgroups boot
rc-update add local default
rc-update add auditd default
```

### 8.7 Optional cgroup-device BPF filter

With `--enable-device-bpf`, the script creates:

```text
/usr/local/libexec/toor-dev-filter.bpf.c
/usr/local/libexec/toor-build-dev-filter
/etc/init.d/toor-bpf-devfilter
```

The BPF filter denies a small set of sensitive device nodes under the `/sys/fs/cgroup/toor` cgroup. It is intentionally conservative and should be expanded only after local device requirements are known.

### 8.8 Boot command-line fragment

Writes:

```text
/etc/kernel/cmdline.toor-selinux
```

Default fragment shape:

```text
audit=1 selinux=1 enforcing=0 lsm=lockdown,yama,integrity,selinux cgroup_no_v1=all
```

With lockdown:

```text
audit=1 selinux=1 enforcing=0 lsm=lockdown,yama,integrity,selinux cgroup_no_v1=all lockdown=integrity
```

The script can optionally patch `/etc/default/grub`, but it does not assume GRUB by default.

---

## 9. Staged rollout sequences for script command syntax

### 9.1 Stage 0: preflight and backup

Recommended manual checks:

```bash
id
eselect profile show
readlink -f /etc/portage/make.profile
uname -a
stat -fc %T /sys/fs/cgroup || true
cat /proc/cmdline
cp -a /etc/portage /root/portage.backup.$(date +%Y%m%d%H%M%S)
cp -a /etc/selinux /root/selinux.backup.$(date +%Y%m%d%H%M%S) 2>/dev/null || true
cp -a /usr/src/linux/.config /root/kernel.config.backup.$(date +%Y%m%d%H%M%S)
```

### 9.2 Stage 1: dry-run full plan

```bash
python3 gentoo_toor_selinux_bootstrap.py \
  --kernel-src /usr/src/linux \
  --kernel-config /usr/src/linux/.config \
  --policy-type targeted \
  --policy-types targeted \
  --selinux-mode permissive \
  --enable-device-bpf
```

Review all planned file writes and commands.

### 9.3 Stage 2: create profile, account, OpenRC, SELinux config, and patch kernel config

```bash
chmod +x gentoo_toor_selinux_bootstrap.py

./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --patch-kconfig \
  --run-olddefconfig \
  --policy-type targeted \
  --policy-types targeted \
  --selinux-mode permissive \
  --enable-device-bpf
```

Conservative variant without BPF:

```bash
./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --patch-kconfig \
  --run-olddefconfig \
  --policy-type targeted \
  --policy-types targeted \
  --selinux-mode permissive
```

### 9.4 Stage 3: install userspace packages

Manual package install is preferred for the first host:

```bash
emerge --ask --verbose --changed-use --deep \
  sec-policy/selinux-base \
  sec-policy/selinux-base-policy \
  sec-policy/selinux-openrc \
  sys-apps/policycoreutils \
  sys-apps/selinux-python \
  sys-apps/checkpolicy \
  sys-apps/secilc \
  app-admin/setools \
  sys-process/audit \
  dev-util/bpftool \
  dev-libs/libbpf \
  sys-apps/iproute2

emerge --ask --verbose --changed-use --deep --newuse @world
```

Script-driven variant:

```bash
./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --skip-portage \
  --skip-kernel \
  --skip-openrc \
  --skip-account \
  --skip-selinux-files \
  --skip-cmdline \
  --emerge \
  --enable-device-bpf
```

### 9.5 Stage 4: build and install the kernel

Example manual LLVM path:

```bash
cd /usr/src/linux
make LLVM=1 olddefconfig
make LLVM=1 -j"$(nproc)"
make LLVM=1 modules_install
make install
```

If enforcing module signing later, keep private signing keys out of the deployed host image and document the key path.

### 9.6 Stage 5: first reboot into permissive SELinux

Boot with at least:

```text
audit=1 selinux=1 enforcing=0 lsm=lockdown,yama,integrity,selinux cgroup_no_v1=all
```

Verify:

```bash
getenforce || true
sestatus || true
cat /sys/kernel/security/lsm
stat -fc %T /sys/fs/cgroup
cat /sys/fs/cgroup/cgroup.controllers
rc-status boot
rc-status default
```

Expected cgroup filesystem:

```text
cgroup2fs
```

### 9.7 Stage 6: live SELinux mapping and relabel scheduling

Run after `semanage`, `restorecon`, and policy packages exist:

```bash
./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --skip-portage \
  --skip-kernel \
  --skip-openrc \
  --skip-account \
  --skip-cmdline \
  --configure-selinux \
  --enable-ssh-sysadm-login \
  --schedule-relabel
```

Then reboot for relabel if scheduled.

### 9.8 Stage 7: verify `toor` behavior

```bash
getent passwd root toor
id toor
ssh toor@host
id
id -Z
echo "$HOME"
cat /proc/$$/cgroup
ps -o pid,user,euser,label,cmd -p $$
semanage login -l | grep -E '^(toor|root|__default__)'
ls -Zd /root /toor
ausearch -m avc,user_avc,selinux_err -ts boot || true
```

Desired shape:

```text
uid=0(root) gid=0(root) groups=0(root),...
toor_u:sysadm_r:sysadm_t:s0-s0:c0.c1023
/toor
```

or fallback:

```text
sysadm_u:sysadm_r:sysadm_t:s0-s0:c0.c1023
```

### 9.9 Stage 8: transition to enforcing

Only after AVCs are understood:

```bash
setenforce 1
sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
```

Update boot command line:

```text
enforcing=1
```

Reboot and verify.

### 9.10 Stage 9: optional lockdown and module-signing hardening

Add after kernel, modules, BPF, and recovery procedures are validated:

```bash
./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --skip-portage \
  --skip-openrc \
  --skip-account \
  --skip-selinux-files \
  --skip-cmdline \
  --patch-kconfig \
  --run-olddefconfig \
  --enforce-module-signing \
  --lockdown integrity
```

Then rebuild and test kernel/module boot. Be aware that lockdown can restrict BPF workflows.

---

## 10. Policy enablement for unified usage on multiple hosts

The single-host script is useful for initial convergence. For a fleet, move from ad hoc live mutation to versioned artifacts.

### 10.1 Recommended multi-host control plane

```text
Git repository
  overlays/local-toor-selinux/
    profiles/toor-selinux-llvm/
    ebuilds/sec-policy/selinux-toor-local/
    ebuilds/sys-kernel/site-kernel-config/
  scripts/gentoo_toor_selinux_bootstrap.py
  kernel/configs/6.18/site.config
  kernel/configs/7.x/site.config
  jenkins/Jenkinsfile
  slurm/build-kernel.sbatch
  slurm/build-world.sbatch
```

### 10.2 Canonicalize the Portage profile

The profile generated by the script should become a maintained overlay asset:

```text
/var/db/repos/company-overlay/profiles/toor-selinux-llvm
```

Set:

```text
parent = gentoo:<existing-profile>
USE += selinux audit -systemd
SELINUX_POLICY_TYPES = targeted
```

Pin policy type per host class:

| Host class | Runtime SELinux type | Built policy types | Notes |
|---|---|---|---|
| Build hosts | `targeted` | `targeted` | Lowest friction. |
| Admin/login hosts | `targeted` | `targeted,mcs` | Keep MCS available if categories are later needed. |
| Compute nodes | `targeted` | `targeted` | Keep policy minimal unless node-local tenants require categories. |
| High-assurance enclaves | `mls` | `mls` | Treat as a separate baseline, not a mixed rollout. |

### 10.3 Package local SELinux policy

Do not rely permanently on one-off `semanage` commands. Create a local package such as:

```text
sec-policy/selinux-toor-local
```

Contents:

```text
files/toor-local.cil
files/toor-semanage.mods
files/toor-restorecon.paths
```

Deployment options:

| Method | Use | Caveat |
|---|---|---|
| `semodule -i toor-local.cil` | Install local allow/type policy. | Requires CIL quality control. |
| `semanage import -f toor-semanage.mods` | Reproduce login/fcontext/boolean/port customizations. | `semanage export` output starts with delete operations and can remove current customizations on target systems.[^semanage-export] |
| ebuild `pkg_postinst` commands | Automate local mapping and relabel reminders. | Must be idempotent and safe under binary package installation. |

Red Hat documents multi-system SELinux deployment via automation and via `semanage` export/import; that pattern maps well to Gentoo if the generated state is stored in your overlay and reviewed.[^selinux-multihost]

### 10.4 Binpkg trust model

Gentoo's GPKG binary package format is executed with superuser privileges during installation. Its registration notes explicitly warn that binary packages must be obtained from trusted sources, and that GPKG uses OpenPGP signatures for authenticity support.[^gentoo-gpkg]

Fleet recommendation:

```text
Build once in a controlled buildroot.
Sign packages and metadata.
Publish through HTTPS or SSH.
Use separate binpkg repositories per profile/ABI/microarchitecture class.
Do not mix unsigned local binpkgs with production hosts.
```

### 10.5 Unified host-class policy

Recommended host classes:

| Class | Profile | Kernel | SELinux | Account | cgroup/BPF |
|---|---|---|---|---|---|
| `builder` | `toor-selinux-llvm` | 6.18.x LTS first | Permissive -> enforcing | `toor` enabled | cgroup only; BPF after validation |
| `admin` | `toor-selinux-llvm` | 6.18.x LTS | Enforcing | `toor` enabled | cgroup + BPF |
| `compute` | `toor-selinux-llvm-compute` | 6.18.x LTS | Enforcing | `toor` optional or key-only | cgroup + BPF; stricter device deny |
| `canary` | `toor-selinux-llvm-canary` | 7.x stable | Enforcing | `toor` enabled | cgroup + BPF + lockdown testing |

---

## 11. Method for adapting an existing system

### 11.1 Existing-system adaptation sequence

1. Inventory current state.
2. Create a backup/snapshot.
3. Run script in dry-run mode.
4. Generate local profile without switching if desired.
5. Switch profile.
6. Rebuild affected packages and `@world`.
7. Patch kernel config and rebuild kernel.
8. Boot permissive SELinux.
9. Configure SELinux login mappings.
10. Relabel.
11. Verify `toor` login.
12. Move to enforcing.
13. Add lockdown/module-signing/BPF hardening only after baseline is stable.

### 11.2 Conservative existing-system commands

Create profile but do not repoint yet:

```bash
./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --no-profile-switch \
  --skip-kernel \
  --skip-openrc \
  --skip-account \
  --skip-selinux-files \
  --skip-cmdline \
  --policy-type targeted \
  --policy-types targeted
```

Inspect:

```bash
find /var/db/repos/local-toor-selinux -maxdepth 4 -type f -print -exec sed -n '1,120p' {} \;
```

Switch profile manually:

```bash
ln -sfn /var/db/repos/local-toor-selinux/profiles/toor-selinux-llvm /etc/portage/make.profile
emerge --ask --verbose --changed-use --deep --newuse @world
```

Then apply account/OpenRC/kernel/SELinux files:

```bash
./gentoo_toor_selinux_bootstrap.py \
  --apply \
  --skip-portage \
  --patch-kconfig \
  --run-olddefconfig \
  --policy-type targeted \
  --policy-types targeted \
  --selinux-mode permissive
```

### 11.3 Rollback points

| Failure point | Rollback |
|---|---|
| Profile causes dependency churn | Restore previous `/etc/portage/make.profile` symlink. |
| Kernel does not boot | Boot previous kernel from bootloader. |
| SELinux prevents login | Boot with `enforcing=0`, or temporarily `selinux=0` only for recovery. |
| `toor` account unwanted | Change shell to `/sbin/nologin`, lock password, remove SSH keys, then remove account only after auditing UID `0` entries. |
| cgroup wrapper causes shell issues | `chsh -s /bin/bash toor` from root console and disable wrapper. |
| BPF filter blocks required devices | Disable `toor-bpf-devfilter` service and reboot or detach program manually. |

---

## 12. Method for default enablement of newly built systems

This section maps the design into the described build pipeline:

```text
Gentoo buildroot
  amd64
  LLVM/Clang
  OpenRC
  no systemd
Jenkins workflows
  custom kernel inside stage3 buildroot
Slurm workload distribution
  multi-host distcc build hosts
custom binpkg repository
custom Gentoo overlay/profile
netboot image sync to netboot server
```

### 12.1 Reference architecture

```text
Git/SCM
  |
  +-- company Gentoo overlay
  |     +-- profiles/toor-selinux-llvm
  |     +-- sec-policy/selinux-toor-local
  |     +-- sys-kernel/company-kernel-config
  |
  +-- kernel source/config repository
  |
  +-- Jenkinsfile
        |
        +-- stage3 fetch
        +-- buildroot hydrate
        +-- overlay sync
        +-- bootstrap script --root $BUILDROOT
        +-- package build via Portage
        +-- kernel build via LLVM=1
        +-- Slurm allocation for distcc workers
        +-- binpkg publish
        +-- netboot image compose
        +-- netboot server sync
```

Gentoo publishes current `amd64` stage3 variants, including OpenRC, hardened SELinux OpenRC, LLVM OpenRC, and related flavors in the autobuild tree.[^gentoo-stage3] For this design, the two most relevant starting points are:

```text
stage3-amd64-llvm-openrc
stage3-amd64-hardened-selinux-openrc
```

Use `stage3-amd64-llvm-openrc` if the LLVM toolchain baseline matters most and SELinux is layered by the script/profile. Use `stage3-amd64-hardened-selinux-openrc` if you want the base image already aligned to Gentoo's hardened SELinux stage and are willing to reconcile toolchain differences.

### 12.2 Jenkins workflow shape

Jenkins Pipeline supports Declarative and Scripted Pipeline syntax through a `Jenkinsfile`.[^jenkins-pipeline] A practical declarative shape:

```groovy
pipeline {
  agent { label 'gentoo-build-controller' }

  options {
    timestamps()
    disableConcurrentBuilds()
  }

  parameters {
    choice(name: 'KERNEL_TRACK', choices: ['6.18', '7.x'], description: 'Kernel branch')
    choice(name: 'SELINUX_TYPE', choices: ['targeted', 'mcs', 'mls'], description: 'Runtime SELinux policy')
    booleanParam(name: 'ENABLE_DEVICE_BPF', defaultValue: true, description: 'Enable cgroup-device BPF filter')
  }

  stages {
    stage('Fetch stage3') {
      steps {
        sh './ci/fetch-stage3.sh amd64 llvm-openrc'
      }
    }

    stage('Hydrate buildroot') {
      steps {
        sh './ci/create-buildroot.sh /srv/buildroots/toor-${BUILD_NUMBER}'
      }
    }

    stage('Apply overlay and bootstrap profile') {
      steps {
        sh '''
          ./gentoo_toor_selinux_bootstrap.py \
            --root /srv/buildroots/toor-${BUILD_NUMBER} \
            --apply \
            --policy-type ${SELINUX_TYPE} \
            --policy-types targeted \
            --selinux-mode permissive \
            --patch-kconfig \
            --run-olddefconfig \
            ${ENABLE_DEVICE_BPF:+--enable-device-bpf}
        '''
      }
    }

    stage('Build packages via Slurm/distcc') {
      steps {
        sh 'sbatch --wait ci/slurm-build-world.sbatch /srv/buildroots/toor-${BUILD_NUMBER}'
      }
    }

    stage('Build kernel') {
      steps {
        sh 'sbatch --wait ci/slurm-build-kernel.sbatch /srv/buildroots/toor-${BUILD_NUMBER} ${KERNEL_TRACK}'
      }
    }

    stage('Publish binpkgs and netboot image') {
      steps {
        sh './ci/publish-artifacts.sh /srv/buildroots/toor-${BUILD_NUMBER}'
      }
    }
  }
}
```

### 12.3 Slurm and distcc integration

Slurm is a scalable cluster workload manager that allocates access to compute resources and runs jobs on allocated nodes.[^slurm-quickstart] `sbatch` submits batch scripts to Slurm.[^slurm-sbatch] `distcc` distributes C, C++, Objective-C, and Objective-C++ compilation across machines and should generate the same results as a local build.[^distcc]

Slurm should schedule the build allocation; distcc should perform compile distribution inside that allocation.

Example Slurm wrapper:

```bash
#!/bin/bash
#SBATCH --job-name=gentoo-world
#SBATCH --nodes=8
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=32
#SBATCH --time=08:00:00
#SBATCH --exclusive

set -euo pipefail
ROOT=${1:?buildroot required}

HOSTS=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | paste -sd, -)
export DISTCC_HOSTS="$HOSTS"
export FEATURES="distcc buildpkg"
export MAKEOPTS="-j$((SLURM_NNODES * SLURM_CPUS_PER_TASK))"
export PKGDIR="/srv/binpkgs/toor-selinux-llvm"

chroot "$ROOT" emerge --buildpkg=y --usepkg=n --verbose --deep --newuse @world
```

Operational constraints:

| Constraint | Recommendation |
|---|---|
| Compiler consistency | Ensure all distcc workers expose the same Clang/GCC version and target triple as the buildroot. |
| Header consistency | Use normal distcc mode for compile distribution; do not leak host system headers into the build. |
| Reproducibility | Keep the Portage profile, USE flags, CFLAGS, LLVM version, binutils/lld version, and kernel config under source control. |
| Security | Treat distcc workers as trusted build infrastructure or isolate them behind a build-only network. |

### 12.4 Kernel build inside stage3 buildroot

Kernel stage outline:

```bash
ROOT=/srv/buildroots/toor-${BUILD_NUMBER}
KERNEL_SRC=/usr/src/linux

chroot "$ROOT" bash -lc '
  set -euo pipefail
  cd /usr/src/linux
  make LLVM=1 olddefconfig
  make LLVM=1 -j"$(nproc)"
  make LLVM=1 modules_install
  make install
'
```

For netboot, prefer deterministic artifact names:

```text
vmlinuz-linux-6.18.x-toor
initramfs-linux-6.18.x-toor.img
System.map-linux-6.18.x-toor
config-linux-6.18.x-toor
modules-linux-6.18.x-toor.tar.zst
```

### 12.5 Binpkg repository publish

Recommended layout:

```text
/srv/binpkgs/
  amd64/
    toor-selinux-llvm/
      targeted/
        6.18/
        7.x/
```

Target hosts should consume the binpkg repository with explicit trust boundaries:

```text
PORTAGE_BINHOST="https://binpkg.example.net/amd64/toor-selinux-llvm/targeted/6.18"
FEATURES="getbinpkg binpkg-request-signature"
```

The exact signature settings depend on your Portage/GPKG policy and key deployment, but the core rule is stable: no unsigned production binpkg feed.

### 12.6 Netboot image composition

A netboot image for SELinux must preserve labels or be able to relabel early. Recommended approaches:

| Root image model | SELinux suitability | Notes |
|---|---:|---|
| ext4 image with xattrs | High | Best for preserving file labels. |
| squashfs with xattrs | High if built with xattrs | Good immutable root. |
| NFS root | Variable | Requires deliberate SELinux label strategy; test before production. |
| tmpfs overlay | Good for runtime, but requires base labels | Ensure lower image labels are correct. |

Netboot sync shape:

```bash
rsync -aHAX --delete \
  /srv/artifacts/netboot/toor-selinux-llvm/ \
  netboot.example.net:/srv/tftp/gentoo/toor-selinux-llvm/
```

Kernel command line for permissive first boot:

```text
ip=dhcp audit=1 selinux=1 enforcing=0 lsm=lockdown,yama,integrity,selinux cgroup_no_v1=all
```

Production enforcing command line:

```text
ip=dhcp audit=1 selinux=1 enforcing=1 lsm=lockdown,yama,integrity,selinux cgroup_no_v1=all lockdown=integrity
```

### 12.7 Default enablement sequence for new builds

1. Jenkins fetches current stage3.
2. Jenkins hydrates buildroot.
3. Overlay is mounted or synchronized into `/var/db/repos/company-overlay`.
4. `/etc/portage/make.profile` is set to the company `toor-selinux-llvm` profile.
5. The script runs against `--root $BUILDROOT`.
6. `emerge --buildpkg=y --usepkg=n @world` creates binpkgs.
7. Kernel is built with `LLVM=1` and versioned config.
8. SELinux local policy package is installed into the image.
9. Filesystem is labeled inside buildroot where possible.
10. Netboot image is composed with labels preserved.
11. Artifacts are signed and published.
12. Canary hosts boot permissive.
13. AVCs are resolved.
14. Fleet moves to enforcing.
15. Lockdown and module-signature enforcement are introduced after recovery and BPF flows are validated.

### 12.8 Default production posture

For a mature build pipeline, the desired final state is:

```text
Profile: company-overlay:toor-selinux-llvm
Kernel: 6.18.x longterm for production, 7.x for canary
Init: OpenRC
Cgroups: unified v2
SELinux: targeted, enforcing
Root: break-glass only
toor: UID 0, /toor, SELinux-mapped, cgroup-wrapped
Audit: enabled at boot
BPF device filter: enabled after validation
Lockdown: integrity after BPF/module workflow testing
Module signing: enforced only after all modules are signed reproducibly
Binpkgs: signed, HTTPS/SSH only, per-profile/per-kernel-track repository
```

---

## 13. Operational verification checklist

Run on every canary before promoting to fleet:

```bash
# Identity
getent passwd root toor
id toor

# SELinux
getenforce
sestatus
id -Z
semanage login -l | grep -E '^(toor|root|__default__)'
semanage user -l | grep -E '^(toor_u|sysadm_u|root)'
ls -Zd /root /toor

# Audit
rc-service auditd status
ausearch -m avc,user_avc,selinux_err -ts boot || true

# LSM/kernel
cat /sys/kernel/security/lsm
cat /sys/kernel/security/lockdown 2>/dev/null || true
zgrep -E 'CONFIG_SECURITY_SELINUX|CONFIG_CGROUP_BPF|CONFIG_MODULE_SIG|CONFIG_LSM' /proc/config.gz 2>/dev/null || true

# cgroup v2
stat -fc %T /sys/fs/cgroup
cat /sys/fs/cgroup/cgroup.controllers
cat /proc/$$/cgroup
ls -l /sys/fs/cgroup/toor

# BPF filter, if enabled
bpftool cgroup tree | grep -A4 toor || true
bpftool prog show | grep -i cgroup || true

# Device denial smoke tests, if policy permits safe testing
head -c 1 /dev/kmsg >/dev/null 2>&1 && echo UNEXPECTED || echo expected-deny-or-permission-fail
```

---

## 14. Residual risks

| Risk | Residual status |
|---|---|
| UID `0` ambiguity | Unresolved by design. SELinux context becomes the primary distinction layer. |
| Shared `sysadm_t` scope | If `toor` uses `sysadm_t`, any `sysadm_t` policy change affects all users in that domain. A custom `toor_t` is the long-term improvement. |
| BPF and lockdown ordering | Lockdown can restrict BPF usage. Attach and test device filters before enforcing lockdown fleet-wide. |
| Module signing recovery | Enforced module signing can break out-of-tree hardware modules and rescue workflows if keys are mishandled. |
| Netboot label integrity | Netboot roots must preserve SELinux xattrs or relabel correctly before enforcing. |
| Binpkg trust | Binary packages execute privileged code during installation; only signed trusted feeds should be used. |

---

## 15. Recommended next engineering iteration

The script currently maps `toor` to `toor_u:sysadm_r:sysadm_t` or falls back to `sysadm_u`. The better long-term design is a custom domain:

```text
toor_u:toor_r:toor_t
```

That allows:

```bash
semanage permissive -a toor_t
```

without making all `sysadm_t` sessions permissive.

A follow-on package should provide:

```text
sec-policy/selinux-toor-local
  toor_u definition
  toor_r role
  toor_t domain
  allow rules for intended admin surface
  denies/no rules for policy loading, raw devices, module loading, kexec, BPF mutation, and relabeling where appropriate
```

This would move the posture from:

```text
root-equivalent account with SELinux admin-domain labeling
```

toward:

```text
root-equivalent account constrained by a site-specific administrative MAC domain
```

That is the Linux version closest in spirit to the FreeBSD `toor` convenience model and the Solaris RBAC maturity model, while remaining native to Gentoo, OpenRC, Portage, and custom-kernel operations.

---

## Sources

[^kernel-org]: Linux Kernel Archives, current release table showing `7.0.10` stable and `6.18.33` longterm, 2026-05-23. https://www.kernel.org/

[^portage-profile]: Portage `portage(5)` profile documentation, including `parent` cascading profiles. https://dev.gentoo.org/~zmedico/portage/doc/man/portage.5.html

[^freebsd-toor]: FreeBSD FAQ, “What is this UID 0 toor account?” https://docs.freebsd.org/zh-tw/books/faq/

[^solaris-root-role]: Oracle Solaris documentation, “Changing Whether root Is a User or a Role,” including `rolemod -K type=normal root`. https://docs.oracle.com/cd/E36784_01/html/E37123/rbactask-21.html

[^semanage]: `semanage(8)` Linux man page, login/user mappings and policy management. https://man7.org/linux/man-pages/man8/semanage.8.html

[^gentoo-selinux-base-policy]: Gentoo package metadata for `sec-policy/selinux-base-policy`, including policy type flags `mcs`, `mls`, `strict`, and `targeted`. https://packages.gentoo.org/packages/sec-policy/selinux-base-policy

[^gentoo-selinux-openrc]: Gentoo package metadata for `sec-policy/selinux-openrc`, OpenRC SELinux policy and policy type flags. https://packages.gentoo.org/packages/sec-policy/selinux-openrc

[^gentoo-selinux-python]: Gentoo package metadata for `sys-apps/selinux-python`, including `semanage`, `sepolicy`, and `sepolgen`. https://packages.gentoo.org/packages/sys-apps/selinux-python

[^openrc-cgroup]: OpenRC `rc.conf` comments documenting `rc_cgroup_mode="unified"` as mounting cgroup v2 on `/sys/fs/cgroup`. https://github.com/OpenRC/openrc/blob/master/etc/rc.conf

[^cgroup-v2-device]: Linux kernel cgroup v2 documentation, device controller implemented using cgroup BPF. https://docs.kernel.org/admin-guide/cgroup-v2.html

[^kernel-lockdown]: `kernel_lockdown(7)` Linux manual page, lockdown purpose and restricted interfaces. https://man7.org/linux/man-pages/man7/kernel_lockdown.7.html

[^module-signing]: Linux kernel module signing documentation. https://docs.kernel.org/admin-guide/module-signing.html

[^selinux-mls]: Red Hat SELinux MLS documentation. https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/html/selinux_users_and_administrators_guide/mls

[^selinux-project-permissive]: SELinux Project notebook, `semanage permissive` and `typepermissive`. https://github.com/SELinuxProject/selinux-notebook/blob/main/src/policy_store_config_files.md

[^redhat-permissive-domain]: Red Hat blog guidance on using `semanage permissive` for one domain while the rest of the system remains enforcing. https://www.redhat.com/en/blog/semanage-keep-selinux-enforcing

[^semanage-export]: `semanage-export(8)` Linux man page, export/import behavior and warning about removing current customizations on import target. https://man7.org/linux/man-pages/man8/semanage-export.8.html

[^selinux-multihost]: Red Hat SELinux documentation, deploying same SELinux configuration on multiple systems. https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html/using_selinux/deploying-the-same-selinux-configuration-on-multiple-systems_using-selinux

[^gentoo-gpkg]: IANA media type registration for `application/vnd.gentoo.gpkg`, including security considerations and OpenPGP signature notes. https://www.iana.org/assignments/media-types/application/vnd.gentoo.gpkg

[^gentoo-stage3]: Gentoo amd64 autobuild stage3 index, including OpenRC, LLVM OpenRC, and hardened SELinux OpenRC stage variants. https://ftp.riken.jp/Linux/gentoo/releases/amd64/autobuilds/

[^jenkins-pipeline]: Jenkins Pipeline documentation. https://www.jenkins.io/doc/book/pipeline/

[^slurm-quickstart]: Slurm Quick Start User Guide. https://slurm.schedmd.com/quickstart.html

[^slurm-sbatch]: Slurm `sbatch` documentation. https://slurm.schedmd.com/sbatch.html

[^distcc]: distcc project description. https://www.distcc.org/
