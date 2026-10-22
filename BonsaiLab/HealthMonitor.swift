import Foundation

final class HealthMonitor: @unchecked Sendable {
    static let shared = HealthMonitor()
    private let queue = DispatchQueue(label: "bonsai.health", qos: .utility)
    private var timer: DispatchSourceTimer?
    private var lastWarnings: Set<String> = []
    private var lastWarningAt = 0.0
    private var speed: Double?
    private var baseline: Double?
    private var configuration: String?
    private var activeRequest: String?
    private var lastProgress = 0.0
    func progress(requestID: String, finished: Bool = false) {
        queue.async {
            if finished { if self.activeRequest == requestID { self.activeRequest = nil } }
            else { self.activeRequest = requestID; self.lastProgress = ProcessInfo.processInfo.systemUptime }
        }
    }
    func observe(speed: Double, configuration: String, isBaseline: Bool) {
        queue.async {
            if self.configuration != configuration { self.baseline = nil; self.configuration = configuration }
            self.speed = speed
            if isBaseline { self.baseline = speed }
        }
    }
    func start() {
        queue.async {
            guard self.timer == nil else { return }
            let timer = DispatchSource.makeTimerSource(queue: self.queue)
            timer.schedule(deadline: .now(), repeating: .seconds(10))
            timer.setEventHandler { [weak self] in self?.sample() }
            self.timer = timer; timer.resume()
        }
    }
    func stop() { queue.async { self.timer?.cancel(); self.timer = nil } }
    private func sample() {
        let probe = BonsaiReadSystemProbe()
        let thermal = ProcessInfo.processInfo.thermalState.rawValue
        var codes = Set(HealthPolicy.warnings(availableMB: probe.phys_footprint_bytes > 0 ? Double(probe.available_bytes) / 1_048_576 : nil,
            thermal: thermal, speed: speed, baseline: baseline))
        let now = ProcessInfo.processInfo.systemUptime
        // A long kernel can be legitimate; this is an observed lack of progress, not a deadlock diagnosis.
        if activeRequest != nil && now - lastProgress > 120 { codes.insert("INFERENCE_NO_PROGRESS_SUSPECTED") }
        if codes != lastWarnings || now - lastWarningAt >= 60 {
            for code in codes { CrashDiagnostics.shared.recordError(severity: "WARNING", type: code) }
            lastWarnings = codes; lastWarningAt = now
        }
        CrashDiagnostics.shared.recordTimelineEvent("RESOURCE_SAMPLE", details: CrashDiagnostics.shared.resourceState())
    }
}
