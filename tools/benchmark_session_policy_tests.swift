import Foundation

@main struct BenchmarkPolicyTests {
    static func main() throws {
        precondition(BenchmarkModelAdmission.accepts(gpuLayers: 56, mmap: true))
        precondition(BenchmarkModelAdmission.accepts(gpuLayers: 99, mmap: true))
        precondition(!BenchmarkModelAdmission.accepts(gpuLayers: 0, mmap: true))
        precondition(!BenchmarkModelAdmission.accepts(gpuLayers: -1, mmap: true))
        precondition(!BenchmarkModelAdmission.accepts(gpuLayers: 56, mmap: false))
        let gate = BenchmarkSessionControl()
        precondition(gate.enterOrdinary())
        precondition(gate.beginSession() == nil, "ordinary inference excludes benchmark")
        gate.leaveOrdinary()
        let session = gate.beginSession()!
        precondition(!gate.enterOrdinary())
        precondition(!gate.beginOperation(session: "wrong", request: "r"))
        precondition(gate.beginOperation(session: session, request: "r"))
        precondition(!gate.beginOperation(session: session, request: "other"))
        gate.cancel(session: session)
        precondition(gate.isCancelled)
        gate.finishOperation(error: nil)
        precondition(gate.beginOperation(session: session, request: "next"))
        precondition(!gate.isCancelled)
        gate.finishOperation(error: nil)
        gate.endSession(session: session)
        precondition(gate.enterOrdinary())
        gate.leaveOrdinary()
        precondition(BenchmarkConfiguration(context: 16384, batch: 16, kv: "Q4_0", flags: 1).isValid(capabilities: 7))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 8, kv: "Q4_0", flags: 1).isValid(capabilities: 7))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 24, kv: "Q4_0", flags: 1).isValid(capabilities: 7))
        precondition(!BenchmarkConfiguration(context: 65536, batch: 16, kv: "Q4_0", flags: 0).isValid(capabilities: 7))
        precondition(!BenchmarkConfiguration(context: 8192, batch: 8, kv: "Q2", flags: 0).isValid(capabilities: 7))
        precondition(!BenchmarkConfiguration(context: 16384, batch: 16, kv: "Q4_0", flags: 1).isValid(capabilities: 6))
        print("Benchmark session exclusivity, cancellation, restore and capability policy: PASS")
    }
}
