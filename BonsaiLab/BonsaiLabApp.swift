import SwiftUI

@main
struct BonsaiLabApp: App {
    init() {
        // Freeze the process launch arm before any UI can schedule the next arm.
        _ = Phase2CMetalTensorLaunchLatch.arm
    }

    var body: some Scene {
        WindowGroup {
            ProductionView()
        }
    }
}
