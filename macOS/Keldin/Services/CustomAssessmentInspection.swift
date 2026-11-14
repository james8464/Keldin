import Foundation

struct CustomAssessmentSelection: Equatable {
    let role: CustomAssessmentSourceMetadata.Role
    let url: URL
}

enum CustomAssessmentInspectionError: LocalizedError, Equatable {
    case invalidSelection
    case invalidResponse
    case rejected(String)
    case busy

    var errorDescription: String? {
        switch self {
        case .invalidSelection:
            String(localized: "Choose at least three distinct question papers and no more than twelve files.")
        case .invalidResponse:
            String(localized: "Keldin could not verify the inspection result. Choose the files again.")
        case let .rejected(message):
            message
        case .busy:
            String(localized: "Wait for the current task to finish before checking a page.")
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

    static func observePage(
        _ page: Int,
        of selection: CustomAssessmentSelection,
        verified: CustomAssessmentSourceMetadata,
        model: String,
        backend: any BackendRunning,
        startAccess: (URL) -> Bool = { $0.startAccessingSecurityScopedResource() },
        stopAccess: (URL) -> Void = { $0.stopAccessingSecurityScopedResource() }
    ) async throws -> CustomPageLayoutObservation {
        guard selection.url.isFileURL, selection.role == verified.role,
              verified.isValid, (1...verified.pageCount).contains(page) else {
            throw CustomAssessmentInspectionError.invalidSelection
        }
        try Task.checkCancellation()
        let scoped = startAccess(selection.url)
        defer { if scoped { stopAccess(selection.url) } }
        let events = try await backend.collect(arguments: [
            "inspect-custom-page-layout", "--source", selection.role.rawValue,
            selection.url.path, "--sha256", verified.sha256,
            "--page", String(page), "--model", model,
        ])
        try Task.checkCancellation()
        var result: CustomPageLayoutObservation?
        for event in events {
            switch event {
            case let .customPageLayout(observation):
                guard result == nil, observation.isValid, observation.role == selection.role,
                      observation.sha256 == verified.sha256, observation.page == page,
                      observation.model == model else {
                    throw CustomAssessmentInspectionError.invalidResponse
                }
                result = observation
            case let .error(message, code):
                if ["custom_layout_rejected", "local_memory_unavailable"].contains(code ?? "") {
                    throw CustomAssessmentInspectionError.rejected(message)
                }
                throw CustomAssessmentInspectionError.invalidResponse
            default:
                continue
            }
        }
        guard let result else { throw CustomAssessmentInspectionError.invalidResponse }
        return result
    }
}
