import Foundation
import UIKit
import Combine

@MainActor final class ScreenOnCoordinator: ObservableObject {
    static let shared = ScreenOnCoordinator()
    @Published private(set) var active = false
    var apiRunning = false { didSet { update() } }
    private var observers: [NSObjectProtocol] = []
    init() {
        for name in [UserDefaults.didChangeNotification, BenchmarkSessionControl.changed] {
            observers.append(NotificationCenter.default.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor in self?.update() }
            })
        }
        update()
    }
    func update() {
        active = ScreenOnPolicy.active(enabled: UserDefaults.standard.bool(forKey: "benchmark_keep_screen_on"),
            api: apiRunning, benchmark: BenchmarkSessionControl.shared.active)
        if UIApplication.shared.isIdleTimerDisabled != active { UIApplication.shared.isIdleTimerDisabled = active }
    }
}
