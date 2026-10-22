import Foundation

/// Bounded JSON values, with explicit nulls for unavailable measurements.
indirect enum DiagnosticValue: Codable, Equatable {
    case null, bool(Bool), number(Double), string(String), array([DiagnosticValue]), object([String: DiagnosticValue])
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([String: DiagnosticValue].self) { self = .object(v) }
        else { self = .array(try c.decode([DiagnosticValue].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .null: try c.encodeNil()
        case .bool(let v): try c.encode(v)
        case .number(let v): if v.isFinite { try c.encode(v) } else { try c.encodeNil() }
        case .string(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        }
    }
    static func from(_ value: Any) -> DiagnosticValue {
        if value is NSNull { return .null }
        if let v = value as? String { return .string(v) }
        if let v = value as? NSNumber {
            if String(cString: v.objCType) == "c" { return .bool(v.boolValue) }
            return v.doubleValue.isFinite ? .number(v.doubleValue) : .null
        }
        if let v = value as? [String: Any] { return .object(v.mapValues(Self.from)) }
        if let v = value as? [Any] { return .array(v.map(Self.from)) }
        return .null
    }
    var foundation: Any {
        switch self {
        case .null: return NSNull()
        case .bool(let v): return v
        case .number(let v): return v.isFinite ? v as Any : NSNull()
        case .string(let v): return v
        case .array(let v): return v.map(\.foundation)
        case .object(let v): return v.mapValues(\.foundation)
        }
    }
}

enum DiagnosticPrivacy {
    static let forbidden: Set<String> = ["prompt", "text", "content", "answer", "system", "history", "authorization", "api_key", "api-key", "password", "token_id", "path", "url", "model_path", "exception_message"]
    static func clean(_ values: [String: DiagnosticValue], depth: Int = 0) -> [String: DiagnosticValue] {
        guard depth < 8 else { return [:] }
        var result: [String: DiagnosticValue] = [:]
        for key in values.keys.sorted().prefix(64) where !forbidden.contains(key.lowercased()) {
            guard key.utf8.count <= 80, let value = values[key] else { continue }
            switch value {
            case .string(let v):
                // No caller-provided freeform strings/paths; safe diagnostic labels only.
                if v.contains("/") || v.contains("\\") || v.localizedCaseInsensitiveContains("bearer ") { result[key] = .string("[redacted]") }
                else { result[key] = .string(String(v.prefix(256))) }
            case .object(let v): result[key] = .object(clean(v, depth: depth + 1))
            case .array(let v): result[key] = .array(v.prefix(200).map { item in
                clean(["value": item], depth: depth + 1)["value"] ?? .null
            })
            default: result[key] = value
            }
        }
        return result
    }
}

enum ScreenOnPolicy {
    static func active(enabled: Bool, api: Bool, benchmark: Bool) -> Bool { enabled && (api || benchmark) }
}

enum HealthPolicy {
    static func warnings(availableMB: Double?, thermal: Int, speed: Double?, baseline: Double?) -> [String] {
        var values: [String] = []
        if let availableMB, availableMB.isFinite, availableMB >= 0, availableMB < 500 { values.append("LOW_MEMORY") }
        if thermal >= 2 { values.append("THERMAL_PRESSURE") }
        if let speed, let baseline, speed.isFinite, baseline.isFinite, speed >= 0, baseline > 0, speed < baseline * 0.7 { values.append("PERFORMANCE_DEGRADATION") }
        return values
    }
}
