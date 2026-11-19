// Decode backend records and represent the selections shown by the app.

// Hardware benchmark samples, metrics and verdicts.

import Foundation

struct BenchmarkSample: Identifiable, Equatable {
    let id = UUID()
    let elapsed: Double
    let cpuLoad: Double
    let cpuThroughputMBs: Double
    let memoryAvailableGB: Double
    let memoryPressurePercent: Double
    let swapUsedGB: Double
    let diskWriteMBs: Double
    let diskReadMBs: Double
    let diskFreeGB: Double
    let smallFileMS: Double
    let networkLatencyMS: Double?
    let networkDownloadMBs: Double?
    let ollamaLatencyMS: Double?
    let thermalSpeedLimitPercent: Double?
    let pdfPagesPerSecond: Double

    var networkLatencyDisplayMS: Double {
        networkLatencyMS ?? 0
    }

    var thermalSpeedLimitDisplayPercent: Double {
        thermalSpeedLimitPercent ?? 100
    }
}

struct BenchmarkMetric: Identifiable, Equatable {
    let id = UUID()
    let name: String
    let value: Double?
    let unit: String?
    let detail: String?
    let score: Double?

    var displayValue: String {
        displayValue(locale: .current)
    }

    func displayValue(locale: Locale) -> String {
        if let value {
            let formatted = value.formatted(.number.precision(.fractionLength(0...2)).locale(locale))
            if let unit, !unit.isEmpty {
                return "\(formatted) \(NativeInterfaceCopy.benchmarkUnit(unit, locale: locale))"
            }
            return formatted
        }
        if let detail { return NativeInterfaceCopy.benchmarkText(detail, locale: locale) }
        return String(localized: InterfaceText.localizedResource("Unknown", locale: locale))
    }
}

struct BenchmarkVerdict: Equatable {
    let score: Double
    let verdict: String
    let detail: String

    var validatedScore: Double? {
        score.isFinite && (0 ... 1).contains(score) ? score : nil
    }

    static let invalidScoreMessage = "The benchmark returned an invalid score."
}
