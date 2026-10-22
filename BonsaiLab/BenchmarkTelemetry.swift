import Foundation
import Metal
import UIKit

/// Samples are an observed peak, never a claim of an unsampled absolute maximum.
final class BenchmarkTelemetry: @unchecked Sendable {
    private let lock = NSLock()
    private let queue = DispatchQueue(label: "bonsai.benchmark.telemetry")
    private var timer: DispatchSourceTimer?
    private var peak: UInt64 = 0
    private var available: UInt64 = UInt64.max
    private var metal: UInt64 = 0
    private var samples = 0
    private var thermal = 0
    init() {
        sample()
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now(), repeating: .milliseconds(50))
        timer.setEventHandler { [weak self] in self?.sample() }
        self.timer = timer
        timer.resume()
    }
    func sample() {
        let p = BonsaiReadSystemProbe()
        lock.lock(); defer { lock.unlock() }
        peak = max(peak, p.phys_footprint_bytes)
        available = min(available, p.available_bytes)
        metal = max(metal, p.metal_allocated_bytes)
        thermal = max(thermal, ProcessInfo.processInfo.thermalState.rawValue)
        samples += 1
    }
    func finish() -> [String: Any] {
        timer?.cancel(); timer = nil
        queue.sync {}
        sample()
        lock.lock(); defer { lock.unlock() }
        return ["sampled_peak_footprint_bytes": peak, "min_available_bytes": available,
                "sampled_peak_metal_bytes": metal, "samples": samples,
                "interval_ms": 50, "max_thermal_state": thermal]
    }
    deinit { timer?.cancel() }
    static func counters() -> [UInt64] { (0..<10).map { BonsaiBenchmarkCounter(Int32($0)) } }
    static func evidence() -> [String: Any] {
        B16RuntimeEvidence.snapshot(sourceSHA: BonsaiCertificationBuildIdentity.sourceGitSHA,
            buildNumber: Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "unknown")
    }
    static func hardware() -> [String: Any] {
        var system = utsname(); uname(&system)
        let machine = withUnsafePointer(to: &system.machine) { ptr in
            ptr.withMemoryRebound(to: CChar.self, capacity: 256) { String(cString: $0) }
        }
        let gpu = MTLCreateSystemDefaultDevice()?.name ?? "unknown"
        let memory = ProcessInfo.processInfo.physicalMemory
        return ["machine": machine, "gpu": gpu, "physical_memory_bytes": memory,
                "eligible": UIDevice.current.userInterfaceIdiom == .pad && gpu.contains("M5")
                    && memory >= 11 * 1_073_741_824 && memory < 13 * 1_073_741_824,
                "thermal_state": ProcessInfo.processInfo.thermalState.rawValue]
    }
}
