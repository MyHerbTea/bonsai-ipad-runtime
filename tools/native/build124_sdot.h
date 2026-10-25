/* Isolated Apple ARM64 dot-product candidate; unsupported hosts fail closed. */
#if defined(__APPLE__) && defined(__aarch64__) && defined(__clang__)
#include <stddef.h>
#include <sys/types.h>
#include <sys/sysctl.h>
#define BONSAI_CPU_SDOT 1
static int bonsai_sdot_supported(void) {
    int enabled=0;size_t size=sizeof(enabled);
    return sysctlbyname("hw.optional.arm.FEAT_DotProd",&enabled,&size,NULL,0)==0 &&
        size==sizeof(enabled) && enabled!=0;
}
#else
#define BONSAI_CPU_SDOT 0
static int bonsai_sdot_supported(void) { return 0; }
#endif
