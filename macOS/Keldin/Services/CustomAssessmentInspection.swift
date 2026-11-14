import Foundation

struct CustomAssessmentSelection: Equatable {
    let role: CustomAssessmentSourceMetadata.Role
    let url: URL
}

enum CustomAssessmentInspectionError: LocalizedError, Equatable {
    case invalidSelection
    case invalidResponse
    case rejected(String)

    var errorDescription: String? {
        switch self {
        case .invalidSelection:
            String(localized: "Choose at least three distinct question papers and no more than twelve files.")
        case .invalidResponse:
            String(localized: "Keldin could not verify the inspection result. Choose the files again.")
        case let .rejected(message):
            message
        }
    }
}

@MainActor
enum CustomAssessmentInspection {
    static func inspect(
        _ selections: [CustomAssessmentSelection],
        backend: any BackendRunning,
        startAccess: (URL) -> Bool = { $0.startAccessingSecurityScopedResource() },
        stopAccess: (URL) -> Void = { $0.stopAccessingSecurityScopedResource() }
    ) async throws -> [CustomAssessmentSourceMetadata] {
        guard (3...12).contains(selections.count),
              selections.filter({ $0.role == .questionPaper }).count >= 3,
              selections.allSatisfy({ $0.url.isFileURL }),
              Set(selections.map { $0.url.standardizedFileURL }).count == selections.count else {
            throw CustomAssessmentInspectionError.invalidSelection
        }
        try Task.checkCancellation()
        let scoped = selections.map(\.url).filter { startAccess($0) }
        defer { scoped.reversed().forEach { stopAccess($0) } }
        let arguments = ["inspect-custom-assessment"] + selections.flatMap {
            ["--source", $0.role.rawValue, $0.url.path]
        }
        let events = try await backend.collect(arguments: arguments)
        try Task.checkCancellation()
        // A partial or repeated result must not override a backend failure.
        for event in events {
            if case let .error(message, code) = event {
                if code == "custom_source_rejected" {
                    throw CustomAssessmentInspectionError.rejected(message)
                }
                throw CustomAssessmentInspectionError.invalidResponse
            }
        }
        let results = events.compactMap { event -> [CustomAssessmentSourceMetadata]? in
            if case let .customAssessmentSources(result) = event { return result }
            return nil
        }
        guard results.count == 1,
              let result = results.first,
              result.map(\.role) == selections.map(\.role) else {
            throw CustomAssessmentInspectionError.invalidResponse
        }
        return result
    }
}
