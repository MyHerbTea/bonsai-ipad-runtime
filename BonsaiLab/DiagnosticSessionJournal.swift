import Foundation

/// Accessed only on the diagnostic serial queue. Old evidence is immutable until recovery succeeds.
final class DiagnosticSessionJournal {
    enum JournalError: Error { case recoveryPending }
    private let url: URL
    private var ready = false
    init(url: URL) { self.url = url }
    func recover(_ action: () throws -> Void) rethrows {
        try action()
        ready = true
    }
    func write(_ data: Data) throws {
        guard ready else { throw JournalError.recoveryPending }
        try data.write(to: url, options: .atomic)
    }
}
