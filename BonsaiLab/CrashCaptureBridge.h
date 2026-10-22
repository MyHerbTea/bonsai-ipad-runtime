#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct { uint32_t magic; uint32_t signal_number; uint64_t program_counter; uint64_t fault_address; } BonsaiCrashRecord;
bool BonsaiCrashInstall(const char * path);
bool BonsaiCrashRead(const char * path, BonsaiCrashRecord * record);
#ifdef __cplusplus
}
#endif
#ifdef __OBJC__
#import <Foundation/Foundation.h>
FOUNDATION_EXPORT NSString * BonsaiCrashBinaryImagesJSON(void);
#endif
