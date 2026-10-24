#include "BenchmarkNativeBridge.h"
#include <dlfcn.h>

extern "C" bool BonsaiCPUSamplingAvailable(void) {
    return dlsym(RTLD_DEFAULT,"BonsaiNativeCPUSamplingConfigure") && dlsym(RTLD_DEFAULT,"BonsaiNativeCPUSamplingCounter");
}
extern "C" int BonsaiCPUSamplingConfigure(int counting,int period) {
    using Fn=int(*)(int,int);static Fn fn=reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT,"BonsaiNativeCPUSamplingConfigure"));return fn?fn(counting,period):0;
}
extern "C" uint64_t BonsaiCPUSamplingCounter(int index) {
    using Fn=uint64_t(*)(int);static Fn fn=reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT,"BonsaiNativeCPUSamplingCounter"));return fn?fn(index):0;
}
extern "C" bool BonsaiCPUTimeAvailable(void) {
    return dlsym(RTLD_DEFAULT,"BonsaiNativeCPUTimeReset") &&
        dlsym(RTLD_DEFAULT,"BonsaiNativeCPUTimeEnable") && dlsym(RTLD_DEFAULT,"BonsaiNativeCPUTimeCounter");
}
extern "C" void BonsaiCPUTimeReset(void) {
    using Fn=void(*)(void); static Fn fn=reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT,"BonsaiNativeCPUTimeReset")); if(fn)fn();
}
extern "C" void BonsaiCPUTimeEnable(int enabled) {
    using Fn=void(*)(int); static Fn fn=reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT,"BonsaiNativeCPUTimeEnable")); if(fn)fn(enabled);
}
extern "C" uint64_t BonsaiCPUTimeCounter(int index) {
    using Fn=uint64_t(*)(int); static Fn fn=reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT,"BonsaiNativeCPUTimeCounter")); return fn?fn(index):0;
}

extern "C" bool BonsaiCPUAvailable(void) {
    return dlsym(RTLD_DEFAULT, "BonsaiNativeCPUCounter") != nullptr &&
        dlsym(RTLD_DEFAULT, "BonsaiNativeCPUConfigure") != nullptr &&
        dlsym(RTLD_DEFAULT, "BonsaiNativeCPUCapabilities") != nullptr;
}
extern "C" uint64_t BonsaiCPUCounter(int index) {
    using Fn = uint64_t (*)(int);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeCPUCounter"));
    return fn ? fn(index) : 0;
}

extern "C" bool BonsaiProfileAvailable(void) { return dlsym(RTLD_DEFAULT, "BonsaiNativeProfileCounter") != nullptr; }
extern "C" void BonsaiProfileReset(void) {
    using Fn = void (*)(void);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeProfileReset")); if (fn) fn();
}
extern "C" void BonsaiProfileEnable(int enabled) {
    using Fn = void (*)(int);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeProfileEnable")); if (fn) fn(enabled);
}
extern "C" uint64_t BonsaiProfileCounter(int index) {
    using Fn = uint64_t (*)(int);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeProfileCounter")); return fn ? fn(index) : 0;
}

// Missing framework exports fail closed. The IPA build verifies all three
// symbols in the linked framework; dlsym keeps non-benchmark builds linkable.
extern "C" int32_t BonsaiBenchmarkConfigure(int32_t flags) {
    using Fn = int32_t (*)(int32_t);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeBenchmarkConfigure"));
    return fn ? fn(flags) : 0;
}
extern "C" uint32_t BonsaiBenchmarkCapabilities(void) {
    using Fn = uint32_t (*)(void);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeBenchmarkCapabilities"));
    return fn ? fn() : 0;
}
extern "C" uint64_t BonsaiBenchmarkCounter(int index) {
    using Fn = uint64_t (*)(int);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeBenchmarkCounter"));
    return fn ? fn(index) : 0;
}

extern "C" void BonsaiBenchmarkBeginRequest(void) {
    using Fn = void (*)(void);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeBenchmarkBeginRequest"));
    if (fn) fn();
}
extern "C" int64_t BonsaiBenchmarkObservation(int index) {
    using Fn = int64_t (*)(int);
    static Fn fn = reinterpret_cast<Fn>(dlsym(RTLD_DEFAULT, "BonsaiNativeBenchmarkObservation"));
    return fn ? fn(index) : 0;
}
