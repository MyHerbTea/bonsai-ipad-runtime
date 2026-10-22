#include "CrashCaptureBridge.h"
#include <cassert>
#include <signal.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <unistd.h>
#include <string>

// Standalone macOS subprocess, never an iOS production crash trigger.
int main() {
    std::string path = std::string(getenv("TMPDIR") ?: "/tmp/") + "bonsai-crash-" + std::to_string(getpid());
    pid_t child = fork();
    assert(child >= 0);
    if (child == 0) {
        struct rlimit limit = {0, 0}; setrlimit(RLIMIT_CORE, &limit);
        if (!BonsaiCrashInstall(path.c_str())) _exit(10);
        raise(SIGABRT);
        _exit(11);
    }
    int status = 0; waitpid(child, &status, 0);
    assert(WIFSIGNALED(status) && WTERMSIG(status) == SIGABRT);
    BonsaiCrashRecord record = {};
    assert(BonsaiCrashRead(path.c_str(), &record));
    assert(record.signal_number == SIGABRT && record.program_counter != 0);
    unlink(path.c_str());
    assert(!BonsaiCrashRead(path.c_str(), &record));
    puts("Build117 signal capture in isolated subprocess: PASS");
}
