use core::ffi::c_long;
#[cfg(not(test))]
use core::ffi::{c_char, c_int, c_void};
#[cfg(not(test))]
use std::mem;
#[cfg(not(test))]
use std::sync::atomic::{AtomicI32, Ordering};
#[cfg(not(test))]
use std::sync::OnceLock;

#[cfg(test)]
const EV_SYN: u16 = 0;
const EV_KEY: u16 = 1;
const EV_ABS: u16 = 3;
const BTN_LEFT: u16 = 0x110;
const BTN_RIGHT: u16 = 0x111;
const BTN_MIDDLE: u16 = 0x112;

#[cfg(not(test))]
const RTLD_NEXT: *mut c_void = -1_isize as *mut c_void;
#[cfg(not(test))]
const UINPUT_PATH: &[u8] = b"/dev/uinput";
#[cfg(not(test))]
const RELAY_PATH: &[u8] =
    b"/run/user/1000/4deus-mod-rustdesk-pointer-relay.sock\0";
#[cfg(not(test))]
const AF_UNIX: c_int = 1;
#[cfg(not(test))]
const SOCK_DGRAM: c_int = 2;
#[cfg(not(test))]
const SOCK_NONBLOCK: c_int = 0x800;
#[cfg(not(test))]
const SOCK_CLOEXEC: c_int = 0x80000;
#[cfg(not(test))]
const MSG_DONTWAIT: c_int = 0x40;
#[cfg(not(test))]
const MSG_NOSIGNAL: c_int = 0x4000;

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct TimeVal {
    seconds: c_long,
    microseconds: c_long,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct InputEvent {
    time: TimeVal,
    event_type: u16,
    code: u16,
    value: i32,
}

#[cfg(not(test))]
#[repr(C)]
struct SockAddrUn {
    family: u16,
    path: [c_char; 108],
}

#[cfg(not(test))]
type WriteFn =
    unsafe extern "C" fn(c_int, *const c_void, usize) -> isize;

#[cfg(not(test))]
extern "C" {
    fn dlsym(handle: *mut c_void, symbol: *const c_char) -> *mut c_void;
    fn readlink(
        path: *const c_char,
        buffer: *mut c_char,
        size: usize,
    ) -> isize;
    fn sendto(
        socket: c_int,
        buffer: *const c_void,
        length: usize,
        flags: c_int,
        address: *const c_void,
        address_length: u32,
    ) -> isize;
    fn socket(domain: c_int, kind: c_int, protocol: c_int) -> c_int;
}

#[cfg(not(test))]
static REAL_WRITE: OnceLock<WriteFn> = OnceLock::new();
#[cfg(not(test))]
static RELAY_SOCKET: OnceLock<c_int> = OnceLock::new();
#[cfg(not(test))]
static RUSTDESK_MOUSE_FD: AtomicI32 = AtomicI32::new(-1);

fn is_mouse_button(event: &InputEvent) -> bool {
    event.event_type == EV_KEY
        && matches!(event.code, BTN_LEFT | BTN_RIGHT | BTN_MIDDLE)
}

fn identifies_pointer(events: &[InputEvent]) -> bool {
    events.iter().any(|event| {
        event.event_type == EV_ABS || is_mouse_button(event)
    })
}

#[cfg(not(test))]
unsafe fn resolve_write() -> WriteFn {
    let address = dlsym(RTLD_NEXT, b"write\0".as_ptr().cast());
    assert!(!address.is_null(), "failed to resolve libc write");
    mem::transmute(address)
}

#[cfg(not(test))]
fn is_uinput_fd(fd: c_int) -> bool {
    let descriptor_path = format!("/proc/self/fd/{fd}\0");
    let mut path = [0_u8; 64];
    let length = unsafe {
        readlink(
            descriptor_path.as_ptr().cast(),
            path.as_mut_ptr().cast(),
            path.len(),
        )
    };
    length > 0 && &path[..length as usize] == UINPUT_PATH
}

#[cfg(not(test))]
fn relay_socket() -> c_int {
    *RELAY_SOCKET.get_or_init(|| unsafe {
        socket(
            AF_UNIX,
            SOCK_DGRAM | SOCK_NONBLOCK | SOCK_CLOEXEC,
            0,
        )
    })
}

#[cfg(not(test))]
fn relay_events(buffer: *const c_void, count: usize) -> bool {
    let socket_fd = relay_socket();
    if socket_fd < 0 {
        return false;
    }
    let mut address = SockAddrUn {
        family: AF_UNIX as u16,
        path: [0; 108],
    };
    if RELAY_PATH.len() > address.path.len() {
        return false;
    }
    for (destination, source) in address.path.iter_mut().zip(RELAY_PATH) {
        *destination = *source as c_char;
    }
    let address_length =
        (mem::size_of::<u16>() + RELAY_PATH.len()) as u32;
    unsafe {
        sendto(
            socket_fd,
            buffer,
            count,
            MSG_DONTWAIT | MSG_NOSIGNAL,
            (&address as *const SockAddrUn).cast(),
            address_length,
        ) == count as isize
    }
}

#[cfg(not(test))]
#[no_mangle]
pub unsafe extern "C" fn write(
    fd: c_int,
    buffer: *const c_void,
    count: usize,
) -> isize {
    let original = *REAL_WRITE.get_or_init(|| resolve_write());
    if buffer.is_null()
        || count == 0
        || count % mem::size_of::<InputEvent>() != 0
    {
        return original(fd, buffer, count);
    }

    let events = std::slice::from_raw_parts(
        buffer.cast::<InputEvent>(),
        count / mem::size_of::<InputEvent>(),
    );
    let tracked_fd = RUSTDESK_MOUSE_FD.load(Ordering::Relaxed);
    if tracked_fd != fd {
        if !identifies_pointer(events) || !is_uinput_fd(fd) {
            return original(fd, buffer, count);
        }
        RUSTDESK_MOUSE_FD.store(fd, Ordering::Relaxed);
    } else if events.iter().any(is_mouse_button) && !is_uinput_fd(fd) {
        RUSTDESK_MOUSE_FD.store(-1, Ordering::Relaxed);
        return original(fd, buffer, count);
    }

    if relay_events(buffer, count) {
        count as isize
    } else {
        original(fd, buffer, count)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn event(event_type: u16, code: u16, value: i32) -> InputEvent {
        InputEvent {
            event_type,
            code,
            value,
            ..InputEvent::default()
        }
    }

    #[test]
    fn identifies_absolute_pointer_and_mouse_buttons() {
        assert!(identifies_pointer(&[event(EV_ABS, 0, 42)]));
        assert!(identifies_pointer(&[event(EV_KEY, BTN_LEFT, 1)]));
        assert!(identifies_pointer(&[event(EV_KEY, BTN_RIGHT, 0)]));
        assert!(identifies_pointer(&[event(EV_KEY, BTN_MIDDLE, 1)]));
    }

    #[test]
    fn ignores_sync_and_keyboard_events() {
        assert!(!identifies_pointer(&[event(EV_SYN, 0, 0)]));
        assert!(!identifies_pointer(&[event(EV_KEY, 30, 1)]));
    }
}
