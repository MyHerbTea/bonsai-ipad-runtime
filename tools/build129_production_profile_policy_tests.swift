import Foundation

@main struct Build129ProfilePolicyTests {
    static func main() {
        guard let profile = BenchmarkSessionMode(rawValue: "production_profile") else {
            fatalError("production profiling mode must exist")
        }
        let control = BenchmarkSessionControl()
        guard control.enterOrdinary() else { fatalError("ordinary admission") }
        precondition(control.beginSession(mode: profile) == nil, "must not acquire while an ordinary request is active")
        control.leaveOrdinary()
        guard let session = control.beginSession(mode: profile) else { fatalError("lease not acquired") }
        precondition(!control.enterOrdinary(), "profiling lease must reject ordinary requests")
        precondition(control.beginSession(mode: profile) == nil, "profiling lease must be exclusive")
        precondition(control.beginOperation(session: session, request: "profile-r1"))
        control.endSession(session: session)
        precondition(control.active, "running operation must retain lease")
        control.finishOperation(error: nil)
        control.endSession(session: session)
        precondition(!control.active && control.enterOrdinary(), "restoration must release lease")
        control.leaveOrdinary()
        precondition(!profile.permits(BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q8_0", flags: 0)), "profile mode must not reconfigure")
        print("Production profile lease policy: PASS")
    }
}
