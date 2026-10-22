#include "BenchmarkNativeBridge.h"
#include <dlfcn.h>

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
