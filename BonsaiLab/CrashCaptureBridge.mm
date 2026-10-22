#include "CrashCaptureBridge.h"
#include <signal.h>
#include <fcntl.h>
#include <unistd.h>
#include <initializer_list>
#include <sys/ucontext.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

static int capture_fd = -1;
static volatile sig_atomic_t capturing = 0;
static unsigned char emergency_stack[64 * 1024];
static void capture_signal(int sig, siginfo_t * info, void * context) {
    if (!capturing) {
        capturing = 1;
        BonsaiCrashRecord record = {0xB0170117, (uint32_t)sig, 0, (uint64_t)(uintptr_t)(info ? info->si_addr : nullptr)};
#if defined(__arm64__)
        if (context) record.program_counter = ((ucontext_t *)context)->uc_mcontext->__ss.__pc;
#elif defined(__x86_64__)
        if (context) record.program_counter = ((ucontext_t *)context)->uc_mcontext->__ss.__rip;
#endif
        if (capture_fd >= 0) { (void)write(capture_fd, &record, sizeof(record)); }
    }
    // Restore default crash semantics; no Swift, allocation, formatting or locks.
    struct sigaction action = {};
    action.sa_handler = SIG_DFL;
    sigemptyset(&action.sa_mask);
    sigaction(sig, &action, nullptr);
    kill(getpid(), sig);
}
extern "C" bool BonsaiCrashInstall(const char * path) {
    if (capture_fd >= 0) return true;
    capture_fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_APPEND, 0600);
    if (capture_fd < 0) return false;
    stack_t stack = {};
    stack.ss_sp = emergency_stack; stack.ss_size = sizeof(emergency_stack);
    if (sigaltstack(&stack, nullptr) != 0) return false;
    struct sigaction action = {};
    action.sa_sigaction = capture_signal;
    sigemptyset(&action.sa_mask);
    action.sa_flags = SA_SIGINFO | SA_ONSTACK;
    for (int sig : {SIGABRT, SIGBUS, SIGFPE, SIGILL, SIGSEGV, SIGTRAP}) {
        if (sigaction(sig, &action, nullptr) != 0) return false;
    }
    return true;
}
extern "C" bool BonsaiCrashRead(const char * path, BonsaiCrashRecord * record) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return false;
    ssize_t size = read(fd, record, sizeof(*record));
    close(fd);
    return size == sizeof(*record) && record->magic == 0xB0170117;
}
NSString * BonsaiCrashBinaryImagesJSON(void) {
    NSMutableArray * images = [NSMutableArray array];
    for (uint32_t i = 0; i < _dyld_image_count(); ++i) {
        const struct mach_header * h = _dyld_get_image_header(i);
        if (!h || h->magic != MH_MAGIC_64) continue;
        const char * imageName = _dyld_get_image_name(i);
        NSString * name = imageName ? [[NSString stringWithUTF8String:imageName] lastPathComponent] : @"unknown";
        // Only app/llama images; system image identities can be supplied by OS crash logs.
        if (![name isEqualToString:@"BonsaiLab"] && ![name isEqualToString:@"llama"]) continue;
        const uint8_t * cursor = (const uint8_t *)h + sizeof(struct mach_header_64);
        for (uint32_t j = 0; j < h->ncmds; ++j) {
            const struct load_command * command = (const struct load_command *)cursor;
            if (command->cmd == LC_UUID) {
                const struct uuid_command * uuid = (const struct uuid_command *)cursor;
                NSUUID * value = [[NSUUID alloc] initWithUUIDBytes:uuid->uuid];
                [images addObject:@{@"name": name, @"uuid": value.UUIDString,
                    @"load_address": [NSString stringWithFormat:@"0x%llx", (unsigned long long)(uintptr_t)h],
                    @"slide": @(_dyld_get_image_vmaddr_slide(i))}];
            }
            if (command->cmdsize < sizeof(struct load_command)) break;
            cursor += command->cmdsize;
        }
    }
    NSData * data = [NSJSONSerialization dataWithJSONObject:images options:0 error:nil];
    return data ? [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding] : @"[]";
}
