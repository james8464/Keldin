// Decode backend records and represent the selections shown by the app.

// Exam board, qualification and catalogue decoding shown by the sidebar.

import Foundation

enum BoardStatus: String, Equatable {
    case ready
    case placeholder

    var title: String {
        switch self {
        case .ready: "Ready"
        case .placeholder: "Coming Soon"
        }
    }
}

enum AssessmentKind: String, Codable, Hashable {
    case fullPaper = "full-paper"
    case questionBank = "question-bank"

    var title: String {
        switch self {
        case .fullPaper: "Full Paper"
        case .questionBank: "Topic Practice"
        }
    }
}

struct PaperOption: Identifiable, Hashable {
    let id: String
    let title: String
    let detail: String
    let readiness: QualificationReadiness
    let assessmentKind: AssessmentKind
    let topicID: String?

    init(
        id: String,
        title: String,
        detail: String,
        readiness: QualificationReadiness,
        assessmentKind: AssessmentKind = .fullPaper,
        topicID: String? = nil
    ) {
        self.id = id
        self.title = title
        self.detail = detail
        self.readiness = readiness
        self.assessmentKind = assessmentKind
        self.topicID = topicID
    }
}

struct QualificationReadiness: Hashable {
    let engineeringValidated: Bool
    let visuallyCalibrated: Bool
    let empiricallyCalibrated: Bool

    var highestLevelTitle: String {
        if empiricallyCalibrated {
            return "Empirically calibrated"
        }
        if visuallyCalibrated {
            return "Visually calibrated"
        }
        if engineeringValidated {
            return "Engineering validated"
        }
        return "Not validated"
    }
}

enum GeneratorContentMode: String, Hashable, Codable {
    case deterministic
    case aiAssisted = "ai-assisted"

    var usesAI: Bool { self == .aiAssisted }

    var title: String {
        switch self {
        case .deterministic: "Built-in constrained generator"
        case .aiAssisted: "AI-assisted generator"
        }
    }

    var systemImage: String {
        switch self {
        case .deterministic: "checklist"
        case .aiAssisted: "sparkles"
        }
    }
}

struct ExamBoardOption: Identifiable, Hashable {
    let id: String
    let subjectID: String
    let subjectTitle: String
    let title: String
    let shortTitle: String
    let systemImage: String
    let status: BoardStatus
    let backendSubject: String?
    let papers: [PaperOption]
    let resourcePath: String
    let contentMode: GeneratorContentMode
    let supportedProviders: [AIProvider]

    var isReady: Bool { status == .ready && backendSubject != nil }
    var usesAI: Bool { contentMode.usesAI }
    var fullPapers: [PaperOption] {
        papers.filter { $0.assessmentKind == .fullPaper }
    }
    var questionBanks: [PaperOption] {
        papers.filter { $0.assessmentKind == .questionBank }
    }

    func supports(_ provider: AIProvider) -> Bool {
        supportedProviders.contains(provider)
    }
}

struct CatalogSubject: Identifiable, Hashable {
    let id: String
    let title: String
    let systemImage: String
    let boards: [ExamBoardOption]
}

enum ExamCatalog {
    /// Keeps the failure so the sidebar can explain an empty catalogue instead
    /// of silently presenting no subjects.
    static let loadResult: Result<[CatalogSubject], CatalogLoadError> = {
        do {
            return .success(try CatalogLoader.load(bundle: .main))
        } catch let error as CatalogLoadError {
            return .failure(error)
        } catch {
            return .failure(.decodingFailed(error.localizedDescription))
        }
    }()

    static var subjects: [CatalogSubject] {
        if case let .success(subjects) = loadResult { subjects } else { [] }
    }

    static var loadError: CatalogLoadError? {
        if case let .failure(error) = loadResult { error } else { nil }
    }

    static var readyBoards: [ExamBoardOption] {
        subjects.flatMap(\.boards).filter(\.isReady)
    }

    static var defaultBoard: ExamBoardOption {
        board(id: "economics-edexcel-a") ?? readyBoards.first ?? ExamBoardOption(
            id: "unknown", subjectID: "unknown", subjectTitle: "Unknown", title: "Unknown",
            shortTitle: "Unknown", systemImage: "doc.text", status: .placeholder,
            backendSubject: nil, papers: [], resourcePath: "",
            contentMode: .deterministic, supportedProviders: []
        )
    }

    static func board(id: String) -> ExamBoardOption? {
        subjects.flatMap(\.boards).first { $0.id == id }
    }
}

enum CatalogLoader {
    static func load(bundle: Bundle) throws -> [CatalogSubject] {
        guard let catalogURL = bundle.url(forResource: "catalog", withExtension: "json") else {
            throw CatalogLoadError.missingResource("catalog.json")
        }
        guard let registryURL = bundle.url(forResource: "generator-registry", withExtension: "json") else {
            throw CatalogLoadError.missingResource("generator-registry.json")
        }
        return try load(
            catalogData: Data(contentsOf: catalogURL),
            registryData: Data(contentsOf: registryURL)
        )
    }

    static func load(catalogData: Data, registryData: Data) throws -> [CatalogSubject] {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        let catalog = try decoder.decode(CatalogDocument.self, from: catalogData)
        let registry = try decoder.decode(GeneratorRegistryDocument.self, from: registryData)
        guard catalog.qualification == "A-Level", registry.qualification == "a-level" else {
            throw CatalogLoadError.qualificationMismatch
        }

        var implementations: [String: GeneratorFamilyDocument] = [:]
        for family in registry.families where family.advertised {
            let key = implementationKey(subject: family.appSubject, board: family.appBoard)
            guard implementations[key] == nil else {
                throw CatalogLoadError.duplicateImplementation(key)
            }
            guard !family.papers.isEmpty else {
                throw CatalogLoadError.emptyImplementation(key)
            }
            implementations[key] = family
        }

        var seenBoards: Set<String> = []
        let subjects = try catalog.subjects.map { subject -> CatalogSubject in
            let boards = try subject.boards.map { board -> ExamBoardOption in
                let key = implementationKey(subject: subject.id, board: board.id)
                guard seenBoards.insert(key).inserted else {
                    throw CatalogLoadError.duplicateBoard(key)
                }
                if let implementation = implementations.removeValue(forKey: key) {
                    return ExamBoardOption(
                        id: key,
                        subjectID: subject.id,
                        subjectTitle: subject.title,
                        title: board.title,
                        shortTitle: board.shortTitle ?? board.title,
                        systemImage: subject.systemImage,
                        status: .ready,
                        backendSubject: implementation.backendSubject,
                        papers: implementation.papers.map {
                            PaperOption(
                                id: $0.id,
                                title: $0.title,
                                detail: $0.detail,
                                readiness: $0.readiness,
                                assessmentKind: $0.assessmentKind,
                                topicID: $0.topicId
                            )
                        },
                        resourcePath: implementation.resourcePath,
                        contentMode: implementation.contentMode,
                        supportedProviders: try implementation.supportedProviders.map {
                            guard let provider = AIProvider(backendID: $0) else {
                                throw CatalogLoadError.unknownProvider($0)
                            }
                            return provider
                        }
                    )
                }
                return ExamBoardOption(
                    id: key,
                    subjectID: subject.id,
                    subjectTitle: subject.title,
                    title: board.title,
                    shortTitle: board.shortTitle ?? board.title,
                    systemImage: subject.systemImage,
                    status: .placeholder,
                    backendSubject: nil,
                    papers: [],
                    resourcePath: "",
                    contentMode: .deterministic,
                    supportedProviders: []
                )
            }
            return CatalogSubject(
                id: subject.id,
                title: subject.title,
                systemImage: subject.systemImage,
                boards: boards
            )
        }
        if let unmatched = implementations.keys.sorted().first {
            throw CatalogLoadError.implementationMissingFromCatalog(unmatched)
        }
        return subjects
    }

    private static func implementationKey(subject: String, board: String) -> String {
        "\(subject)-\(board)"
    }
}

private struct CatalogDocument: Decodable {
    let qualification: String
    let subjects: [CatalogSubjectDocument]
}

private struct CatalogSubjectDocument: Decodable {
    let id: String
    let title: String
    let systemImage: String
    let boards: [CatalogBoardDocument]
}

private struct CatalogBoardDocument: Decodable {
    let id: String
    let title: String
    let shortTitle: String?
}

private struct GeneratorRegistryDocument: Decodable {
    let qualification: String
    let families: [GeneratorFamilyDocument]
}

private struct GeneratorFamilyDocument: Decodable {
    let appSubject: String
    let appBoard: String
    let backendSubject: String
    let resourcePath: String
    let contentMode: GeneratorContentMode
    let supportedProviders: [String]
    let advertised: Bool
    let papers: [GeneratorPaperDocument]
}

private struct GeneratorPaperDocument: Decodable {
    let id: String
    let title: String
    let detail: String
    let checks: [String: Bool]
    let qualification: [String: QualificationLevelDocument]?
    let legacyGates: [String: Bool]
    let assessmentKind: AssessmentKind
    let topicId: String?

    var readiness: QualificationReadiness {
        if let qualification {
            return QualificationReadiness(
                engineeringValidated: qualification["engineering"]?.isPassed ?? false,
                visuallyCalibrated: qualification["visual"]?.isPassed ?? false,
                empiricallyCalibrated: qualification["empirical"]?.isPassed ?? false
            )
        }
        return QualificationReadiness(
            engineeringValidated: legacyGates["release"] ?? false,
            visuallyCalibrated: legacyGates["visual"] ?? false,
            empiricallyCalibrated: legacyGates["difficulty"] ?? false
        )
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case title
        case detail
        case checks
        case qualification
        case gates
        case assessmentKind
        case topicId
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(String.self, forKey: .id)
        title = try values.decode(String.self, forKey: .title)
        detail = try values.decode(String.self, forKey: .detail)
        checks = try values.decodeIfPresent([String: Bool].self, forKey: .checks) ?? [:]
        qualification = try values.decodeIfPresent(
            [String: QualificationLevelDocument].self,
            forKey: .qualification
        )
        legacyGates = try values.decodeIfPresent(
            [String: Bool].self,
            forKey: .gates
        ) ?? [:]
        assessmentKind = try values.decodeIfPresent(
            AssessmentKind.self,
            forKey: .assessmentKind
        ) ?? .fullPaper
        topicId = try values.decodeIfPresent(String.self, forKey: .topicId)
    }
}

private struct QualificationLevelDocument: Decodable {
    let state: String
    let evidence: [String]

    var isPassed: Bool {
        state == "passed" || state == "not_applicable"
    }
}

enum CatalogLoadError: LocalizedError {
    case missingResource(String)
    case qualificationMismatch
    case duplicateImplementation(String)
    case emptyImplementation(String)
    case duplicateBoard(String)
    case implementationMissingFromCatalog(String)
    case unknownProvider(String)
    case decodingFailed(String)

    var errorDescription: String? {
        switch self {
        case let .missingResource(name): "Missing bundled catalog resource: \(name)"
        case .qualificationMismatch: "Catalog and generator registry qualifications do not match."
        case let .duplicateImplementation(id): "Duplicate generator implementation: \(id)"
        case let .emptyImplementation(id): "Advertised generator has no papers: \(id)"
        case let .duplicateBoard(id): "Duplicate catalog board: \(id)"
        case let .implementationMissingFromCatalog(id): "Generator is missing from the app catalog: \(id)"
        case let .unknownProvider(id): "Generator registry has an unknown AI provider: \(id)"
        case let .decodingFailed(detail): "The bundled catalog could not be decoded: \(detail)"
        }
    }
}

enum SidebarItem: Hashable {
    case board(String)
    case frenchBaccalaureat
    case customAssessmentPreview
    case admissionsTests
    case benchmark
    case documents
    case history
}

enum HelpTopic: String, CaseIterable, Identifiable {
    case gettingStarted
    case choosingAModel
    case creatingAPaper
    case frenchBaccalaureat
    case checkingQuality
    case privacy
    case troubleshooting
    case shortcuts

    var id: String { rawValue }

    var title: String {
        String(localized: titleResource)
    }

    var titleResource: LocalizedStringResource {
        switch self {
        case .gettingStarted: "Getting Started"
        case .choosingAModel: "Choosing a Model"
        case .creatingAPaper: "Creating a Paper"
        case .frenchBaccalaureat: "French Baccalauréat · NSI"
        case .checkingQuality: "Checking Quality"
        case .privacy: "Privacy"
        case .troubleshooting: "Troubleshooting"
        case .shortcuts: "Keyboard Shortcuts"
        }
    }

    var systemImage: String {
        switch self {
        case .gettingStarted: "hand.wave"
        case .choosingAModel: "cpu"
        case .creatingAPaper: "doc.badge.plus"
        case .frenchBaccalaureat: "graduationcap"
        case .checkingQuality: "checklist"
        case .privacy: "hand.raised"
        case .troubleshooting: "wrench.and.screwdriver"
        case .shortcuts: "keyboard"
        }
    }
}
