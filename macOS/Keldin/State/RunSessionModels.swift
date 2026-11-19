// Track a single backend run and the documents it collects.

import Foundation

enum RunningOperation {
    case none
    case generation
    case modelPull
    case mlxSetup
}

enum BackendRunIntent {
    case paper, referencePreparation, reviewRecord, modelPull, mlxSetup, mlxDownloadInfo

    var operation: RunningOperation {
        switch self {
        case .paper: .generation
        case .referencePreparation, .reviewRecord, .mlxDownloadInfo: .none
        case .modelPull: .modelPull
        case .mlxSetup: .mlxSetup
        }
    }
}

struct RunDocuments {
    let frameworkID: String?
    let subject: String?
    let paper: String?
    let workingFolder: URL?
    var fileIDs = Set<UUID>()

    init(
        frameworkID: String? = nil,
        subject: String? = nil,
        paper: String? = nil,
        workingFolder: URL? = nil
    ) {
        self.frameworkID = frameworkID
        self.subject = subject
        self.paper = paper
        self.workingFolder = workingFolder
    }
}

struct BackendRun {
    let id = UUID()
    let intent: BackendRunIntent
    var documents: RunDocuments
    let model: String
    let retryTarget: GenerationRetryTarget?
    let errorPresentation: SettingsActionPresentation?
    let selectAfterDownload: Bool
    var ownedJobID: UUID?
    var process: Process?
    var phase = BackendRunPhase.running
    var backendErrorMessage: String?
    var failureKind: GenerationFailureKind = .generationFailed
    var mlxDownloadInfo: MLXDownloadInfo?
    var receivedArtifactRoles = Set<String>()
}

struct GenerationRetryTarget: Equatable {
    let boardID: String
    let paperID: String
    let provider: AIProvider
    let model: String
    let dryRun: Bool
    let output: URL
    let seed: Int?
    let frenchLargePrint: Bool?
}

enum BackendRunPhase {
    case running, cancelling
}
