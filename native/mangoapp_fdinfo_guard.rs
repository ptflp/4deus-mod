use core::ffi::{c_char, c_int, c_void};
use std::ffi::CStr;
use std::mem;
use std::sync::OnceLock;

const EACCES: c_int = 13;
const ENOENT: c_int = 2;
const O_DIRECTORY: c_int = 0o200000;
const O_CLOEXEC: c_int = 0o2000000;
const RTLD_NEXT: *mut c_void = -1_isize as *mut c_void;

type StatFn = unsafe extern "C" fn(*const c_char, *mut c_void) -> c_int;

extern "C" {
    fn __errno_location() -> *mut c_int;
    fn close(fd: c_int) -> c_int;
    fn dlsym(handle: *mut c_void, symbol: *const c_char) -> *mut c_void;
    fn open(path: *const c_char, flags: c_int, ...) -> c_int;
}

static REAL_LSTAT: OnceLock<StatFn> = OnceLock::new();
static REAL_LSTAT64: OnceLock<StatFn> = OnceLock::new();
static REAL_STAT: OnceLock<StatFn> = OnceLock::new();
static REAL_STAT64: OnceLock<StatFn> = OnceLock::new();

unsafe fn resolve(symbol: &'static [u8]) -> StatFn {
    let address = dlsym(RTLD_NEXT, symbol.as_ptr().cast());
    assert!(!address.is_null(), "failed to resolve libc stat function");
    mem::transmute(address)
}

fn is_process_fd_directory(path: &[u8]) -> bool {
    let Some(remainder) = path.strip_prefix(b"/proc/") else {
        return false;
    };
    let Some(separator) = remainder.iter().position(|byte| *byte == b'/')
    else {
        return false;
    };
    let pid = &remainder[..separator];
    let leaf = &remainder[separator..];
    !pid.is_empty()
        && pid.iter().all(u8::is_ascii_digit)
        && matches!(leaf, b"/fd" | b"/fdinfo")
}

unsafe fn inaccessible_process_fd_directory(path: *const c_char) -> bool {
    if path.is_null() {
        return false;
    }

    let bytes = CStr::from_ptr(path).to_bytes();
    if !is_process_fd_directory(bytes) {
        return false;
    }

    let fd = open(path, O_DIRECTORY | O_CLOEXEC);
    if fd >= 0 {
        close(fd);
        return false;
    }

    *__errno_location() == EACCES
}

unsafe fn guarded_stat(
    path: *const c_char,
    buffer: *mut c_void,
    original: StatFn,
) -> c_int {
    if inaccessible_process_fd_directory(path) {
        *__errno_location() = ENOENT;
        return -1;
    }
    original(path, buffer)
}

#[no_mangle]
pub unsafe extern "C" fn lstat(
    path: *const c_char,
    buffer: *mut c_void,
) -> c_int {
    let original = *REAL_LSTAT.get_or_init(|| resolve(b"lstat\0"));
    guarded_stat(path, buffer, original)
}

#[no_mangle]
pub unsafe extern "C" fn lstat64(
    path: *const c_char,
    buffer: *mut c_void,
) -> c_int {
    let original = *REAL_LSTAT64.get_or_init(|| resolve(b"lstat64\0"));
    guarded_stat(path, buffer, original)
}

#[no_mangle]
pub unsafe extern "C" fn stat(
    path: *const c_char,
    buffer: *mut c_void,
) -> c_int {
    let original = *REAL_STAT.get_or_init(|| resolve(b"stat\0"));
    guarded_stat(path, buffer, original)
}

#[no_mangle]
pub unsafe extern "C" fn stat64(
    path: *const c_char,
    buffer: *mut c_void,
) -> c_int {
    let original = *REAL_STAT64.get_or_init(|| resolve(b"stat64\0"));
    guarded_stat(path, buffer, original)
}
