import SwiftUI

@main
struct BonsaiLabApp: App {
    init() {
        // Recover a proven interrupted PTQ1_0 16K/B16 context creation before UI/latch initialization.
        _ = RC126APIStartupLifecycle.recoverInterruptedPTQ1AB16IfNeeded()
        _ = Phase2CMetalTensorLaunchLatch.arm
    }

    var body: some Scene {
        WindowGroup {
            ProductionView()
        }
    }
}
