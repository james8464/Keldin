// Decode backend records and represent the selections shown by the app.

// Events streamed by the Python backend over the JSON-lines bridge.

import Foundation

enum BackendEvent: Equatable {
    case hello(protocolVersion: Int, backendVersion: String, capabilities: [String])
    case progress(stage: String?, message: String, progress: Double?)
    case file(role: String, path: String)
    case done(message: String)
    case error(message: String, code: String? = nil)
    case cancelledAfterSave(message: String, bundle: String)
    case models([String], message: String?)
    case ollamaStatus(installed: Bool, running: Bool, command: String?, message: String?)
    case mlxDownloadInfo(MLXDownloadInfo)
    case localModelGuidance(LocalModelGuidance)
    case customAssessmentSources([CustomAssessmentSourceMetadata])
    case customPageLayout(CustomPageLayoutObservation)
    case benchmarkMetric(BenchmarkMetric)
    case benchmarkSample(BenchmarkSample)
    case benchmarkDone(BenchmarkVerdict)

    init(jsonLine: String) throws {
        let data = Data(jsonLine.utf8)
        let payload = try JSONDecoder().decode(BackendEventPayload.self, from: data)

        switch payload.type {
        case "custom_assessment_sources":
            struct CustomSourcesPayload: Decodable {
                let sources: [CustomAssessmentSourceMetadata]
            }
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let sources = try decoder.decode(CustomSourcesPayload.self, from: data).sources
            guard (3...12).contains(sources.count),
                  sources.filter({ $0.role == .questionPaper }).count >= 3,
                  Set(sources.map(\.sha256)).count == sources.count,
                  sources.allSatisfy(\.isValid) else {
                throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Invalid custom assessment source metadata."))
            }
            self = .customAssessmentSources(sources)
        case "custom_page_layout":
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            let result = try decoder.decode(CustomPageLayoutObservation.self, from: data)
            guard result.isValid else {
                throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Invalid page layout observation."))
            }
            self = .customPageLayout(result)
        case "model_guidance":
            let decoder = JSONDecoder()
            decoder.keyDecodingStrategy = .convertFromSnakeCase
            self = .localModelGuidance(try decoder.decode(LocalModelGuidance.self, from: data))
        case "hello":
            self = .hello(
                protocolVersion: payload.protocolVersion ?? 0,
                backendVersion: payload.backendVersion ?? "Unknown",
                capabilities: payload.capabilities ?? []
            )
        case "progress":
            self = .progress(stage: payload.stage, message: payload.message ?? "", progress: payload.progress)
        case "file":
            self = .file(role: payload.role ?? "file", path: payload.path ?? "")
        case "done":
            self = .done(message: payload.message ?? "Done")
        case "error":
            let message = payload.message ?? "Unknown backend error"
            if payload.code == "cancelled", let bundle = payload.retainedBundle,
               bundle.utf8.count <= 64,
               bundle.range(of: #"\Ansi-2027-v36--?[0-9]{1,19}-[0-9a-f]{12}\z"#, options: .regularExpression) != nil {
                self = .cancelledAfterSave(message: message, bundle: bundle)
            } else {
                self = .error(message: message, code: payload.code)
            }
        case "models":
            self = .models(payload.models ?? [], message: payload.message)
        case "mlx_download_info":
            guard let model = payload.model, let bytes = payload.downloadBytes, let cached = payload.cached else {
                throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Missing MLX download metadata."))
            }
            let info = MLXDownloadInfo(model: model, downloadBytes: bytes, cached: cached, revision: payload.revision)
            guard info.isValid else {
                throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Invalid MLX download metadata."))
            }
            self = .mlxDownloadInfo(info)
        case "ollama_status":
            self = .ollamaStatus(
                installed: payload.installed ?? false,
                running: payload.running ?? false,
                command: payload.command,
                message: payload.message
            )
        case "benchmark_metric":
            self = .benchmarkMetric(
                BenchmarkMetric(
                    name: payload.name ?? "Metric",
                    value: payload.value,
                    unit: payload.unit,
                    detail: payload.detail ?? payload.message,
                    score: payload.score
                )
            )
        case "benchmark_sample":
            self = .benchmarkSample(
                BenchmarkSample(
                    elapsed: payload.elapsed ?? 0,
                    cpuLoad: payload.cpuLoad ?? 0,
                    cpuThroughputMBs: payload.cpuMBs ?? 0,
                    memoryAvailableGB: payload.memoryAvailableGB ?? 0,
                    memoryPressurePercent: payload.memoryPressurePercent ?? 0,
                    swapUsedGB: payload.swapUsedGB ?? 0,
                    diskWriteMBs: payload.diskWriteMBs ?? 0,
                    diskReadMBs: payload.diskReadMBs ?? 0,
                    diskFreeGB: payload.diskFreeGB ?? 0,
                    smallFileMS: payload.smallFileMS ?? 0,
                    networkLatencyMS: payload.networkLatencyMS,
                    networkDownloadMBs: payload.networkDownloadMBs,
                    ollamaLatencyMS: payload.ollamaLatencyMS,
                    thermalSpeedLimitPercent: payload.thermalSpeedLimitPercent,
                    pdfPagesPerSecond: payload.pdfPagesPerSecond ?? 0
                )
            )
        case "benchmark_done":
            guard let score = payload.score else {
                self = .error(message: BenchmarkVerdict.invalidScoreMessage, code: "invalid_benchmark_score")
                return
            }
            let verdict = BenchmarkVerdict(
                score: score,
                verdict: payload.verdict ?? "Unknown",
                detail: payload.detail ?? payload.message ?? ""
            )
            guard verdict.validatedScore != nil else {
                self = .error(message: BenchmarkVerdict.invalidScoreMessage, code: "invalid_benchmark_score")
                return
            }
            self = .benchmarkDone(verdict)
        default:
            self = .progress(stage: payload.type, message: payload.message ?? payload.type, progress: payload.progress)
        }
    }
}


private struct BackendEventPayload: Decodable {
    let protocolVersion: Int?
    let type: String
    let eventID: Int?
    let timestamp: String?
    let jobID: String?
    let backendVersion: String?
    let capabilities: [String]?
    let stage: String?
    let message: String?
    let code: String?
    let retainedBundle: String?
    let role: String?
    let path: String?
    let page: Int?
    let sourcePDF: String?
    let progress: Double?
    let models: [String]?
    let model: String?
    let downloadBytes: Int?
    let cached: Bool?
    let revision: String?
    let installed: Bool?
    let running: Bool?
    let command: String?
    let name: String?
    let value: Double?
    let unit: String?
    let detail: String?
    let score: Double?
    let elapsed: Double?
    let cpuLoad: Double?
    let cpuMBs: Double?
    let memoryAvailableGB: Double?
    let memoryPressurePercent: Double?
    let swapUsedGB: Double?
    let diskWriteMBs: Double?
    let diskReadMBs: Double?
    let diskFreeGB: Double?
    let smallFileMS: Double?
    let networkLatencyMS: Double?
    let networkDownloadMBs: Double?
    let ollamaLatencyMS: Double?
    let thermalSpeedLimitPercent: Double?
    let pdfPagesPerSecond: Double?
    let verdict: String?

    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol"
        case type
        case eventID = "event_id"
        case timestamp
        case jobID = "job_id"
        case backendVersion = "backend_version"
        case capabilities
        case stage
        case message
        case code
        case retainedBundle = "retained_bundle"
        case role
        case path
        case page
        case sourcePDF = "source_pdf"
        case progress
        case models
        case model
        case downloadBytes = "download_bytes"
        case cached
        case revision
        case installed
        case running
        case command
        case name
        case value
        case unit
        case detail
        case score
        case elapsed
        case cpuLoad = "cpu_load"
        case cpuMBs = "cpu_mb_s"
        case memoryAvailableGB = "memory_available_gb"
        case memoryPressurePercent = "memory_pressure_percent"
        case swapUsedGB = "swap_used_gb"
        case diskWriteMBs = "disk_write_mb_s"
        case diskReadMBs = "disk_read_mb_s"
        case diskFreeGB = "disk_free_gb"
        case smallFileMS = "small_file_ms"
        case networkLatencyMS = "network_latency_ms"
        case networkDownloadMBs = "network_download_mb_s"
        case ollamaLatencyMS = "ollama_latency_ms"
        case thermalSpeedLimitPercent = "thermal_speed_limit_percent"
        case pdfPagesPerSecond = "pdf_pages_per_s"
        case verdict
    }
}
