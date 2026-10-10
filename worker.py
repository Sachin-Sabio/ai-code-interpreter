"""Trusted worker: OS restrictions must be installed before submitted code runs."""
import ctypes
import errno
import io
import json
import os
import resource
import sys
import traceback
from contextlib import redirect_stdout


def linux_sandbox():
    # Landlock confines filesystem reads to the Python runtime; no writable paths.
    libc = ctypes.CDLL(None, use_errno=True)
    class Ruleset(ctypes.Structure):
        _fields_ = [('handled_access_fs', ctypes.c_uint64)]
    class PathRule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int)]
    handled = (1 << 13) - 1
    fd = libc.syscall(444, ctypes.byref(Ruleset(handled)), 8, 0)
    if fd < 0:
        raise RuntimeError('Landlock is unavailable; refusing unsandboxed execution')
    try:
        for path in {sys.base_prefix + '/lib', '/usr/lib', '/lib'}:
            if os.path.exists(path):
                parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
                try:
                    rule = PathRule((1 << 2) | (1 << 3), parent)
                    if libc.syscall(445, fd, 1, ctypes.byref(rule), 0) != 0:
                        raise RuntimeError('Landlock rule failed')
                finally:
                    os.close(parent)
        if libc.prctl(38, 1, 0, 0, 0) or libc.syscall(446, fd, 0):
            raise RuntimeError('Landlock restriction failed')
    finally:
        os.close(fd)
    # Default-deny seccomp: no network, process creation, exec, ptrace, or signals.
    sec = ctypes.CDLL('libseccomp.so.2')
    sec.seccomp_init.restype = ctypes.c_void_p
    sec.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    sec.seccomp_load.argtypes = [ctypes.c_void_p]
    sec.seccomp_release.argtypes = [ctypes.c_void_p]
    sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    ctx = sec.seccomp_init(0x00050000 | errno.EPERM)
    if not ctx:
        raise RuntimeError('seccomp initialization failed')
    try:
        for name in '''read write close fstat newfstatat stat lstat statx lseek mmap mprotect munmap brk
        rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack ioctl pread64 readv writev access faccessat
        faccessat2 open openat getdents64 fcntl getcwd readlink readlinkat futex clock_gettime
        clock_nanosleep nanosleep gettimeofday getpid gettid getuid geteuid getgid getegid
        getrandom madvise mremap sched_yield uname getrusage exit exit_group'''.split():
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and sec.seccomp_rule_add(ctx, 0x7fff0000, number, 0):
                raise RuntimeError('seccomp rule failed')
        if sec.seccomp_load(ctx):
            raise RuntimeError('seccomp load failed')
    finally:
        sec.seccomp_release(ctx)


class LimitedOutput(io.StringIO):
    def write(self, value):
        if self.tell() + len(value) > 1_000_000:
            raise RuntimeError('Execution output limit exceeded')
        return super().write(value)


def run(code):
    output = LimitedOutput()
    try:
        with redirect_stdout(output):
            exec(compile(code, '<submitted>', 'exec'), {'__name__': '__main__'})
        return {'success': True, 'output': output.getvalue()}
    except BaseException:
        # The failure result is exactly format_exc(), including its trailing newline.
        return {'success': False, 'output': traceback.format_exc()}


if __name__ == '__main__':
    code = json.load(sys.stdin)['code']
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_000_000, 1_000_000))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if sys.platform == 'linux':
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        linux_sandbox()
    elif sys.platform != 'darwin':
        raise RuntimeError('Unsupported sandbox platform')
    result = run(code)
    sys.stdout.write(json.dumps(result))
