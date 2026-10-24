#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
// Caller serializes inference, synchronizes GPU, and frees the old context first.
// -1 production; 0 baseline; bits 1 TensorOps, 2 five-row fused matvec,
// 4 app batch reuse. Returns 0 if unavailable, invalid or GPU work is in flight.
int32_t BonsaiBenchmarkConfigure(int32_t flags);
uint32_t BonsaiBenchmarkCapabilities(void);
void BonsaiBenchmarkBeginRequest(void);
int64_t BonsaiBenchmarkObservation(int index);
// All values are process-lifetime monotonic; compare request deltas.
// GPU counters cover Metal context command buffers, not just candidate kernels.
// A complete request also requires successful synchronized engine completion.
enum BonsaiBenchmarkCounterIndex {
    BonsaiBenchmarkTensorRoute = 0,
    BonsaiBenchmarkTensorPipeline = 1,
    BonsaiBenchmarkTensorDispatch = 2,
    BonsaiBenchmarkFusedRoute = 3,
    BonsaiBenchmarkFusedPipeline = 4,
    BonsaiBenchmarkFusedDispatch = 5,
    BonsaiBenchmarkGPUSubmitted = 6,
    BonsaiBenchmarkGPUCompleted = 7,
    BonsaiBenchmarkGPUError = 8,
    BonsaiBenchmarkFallback = 9,
    BonsaiBenchmarkCounterCount = 10
};
uint64_t BonsaiBenchmarkCounter(int index);
bool BonsaiProfileAvailable(void);
void BonsaiProfileReset(void);
void BonsaiProfileEnable(int enabled);
uint64_t BonsaiProfileCounter(int index);
bool BonsaiCPUAvailable(void);
uint64_t BonsaiCPUCounter(int index);
bool BonsaiCPUSamplingAvailable(void);
int BonsaiCPUSamplingConfigure(int counting, int period);
uint64_t BonsaiCPUSamplingCounter(int index);
bool BonsaiCPUTimeAvailable(void);
void BonsaiCPUTimeReset(void);
void BonsaiCPUTimeEnable(int enabled);
uint64_t BonsaiCPUTimeCounter(int index);
#ifdef __cplusplus
}
#endif
