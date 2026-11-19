// Decode backend records and represent the selections shown by the app.

// Model providers, distribution mode and local MLX setup state.

import Foundation

enum AIProvider: String, CaseIterable, Identifiable {
    case ollama
    case openAI
    case anthropic
    case deepSeek
    case apple
    case appleIntelligence

    var id: String { rawValue }

    var title: String {
        switch self {
        case .ollama: "Ollama"
        case .openAI: "OpenAI"
        case .anthropic: "Anthropic"
        case .deepSeek: "DeepSeek"
        case .apple: "Local models (MLX)"
        case .appleIntelligence: "Apple Intelligence"
        }
    }

    var subtitle: String {
        switch self {
        case .ollama: "Runs locally via Ollama"
        case .openAI: "Uses an API key"
        case .anthropic: "Uses an API key"
        case .deepSeek: "French NSI only, uses an API key"
        case .apple: "Runs locally on Apple Silicon"
        case .appleIntelligence: "Uses Apple's on-device system model"
        }
    }

    var subtitleResource: LocalizedStringResource {
        LocalizedStringResource(stringLiteral: subtitle)
    }

    var sendsPromptsOffDevice: Bool {
        self == .openAI || self == .anthropic || self == .deepSeek
    }

    var hostedDisclosureResource: LocalizedStringResource {
        if self == .deepSeek {
            return "DeepSeek receives generation prompts, excerpts from the public French references, draft questions, proposed answers and review requests at api.deepseek.com. Requests use your paid API credits. Your key stays in Keychain and is sent only to DeepSeek for authentication. DeepSeek is available for French NSI drafts only."
        }
        switch self {
        case .openAI:
            return "OpenAI receives generation prompts, selected reference context, draft questions and review requests at api.openai.com. Requests use your API credits. Keldin stores your key in Keychain and sends it to OpenAI for authentication."
        case .anthropic:
            return "Anthropic receives generation prompts, selected reference context, draft questions and review requests at api.anthropic.com. Requests use your API credits. Keldin stores your key in Keychain and sends it to Anthropic for authentication."
        default:
            return "Generation stays on this Mac."
        }
    }

    var systemImage: String {
        switch self {
        case .ollama: "desktopcomputer"
        case .openAI: "sparkles"
        case .anthropic: "text.bubble"
        case .deepSeek: "network"
        case .apple: "applelogo"
        case .appleIntelligence: "sparkles"
        }
    }

    var backendID: String {
        switch self {
        case .ollama: "ollama"
        case .openAI: "openai"
        case .anthropic: "anthropic"
        case .deepSeek: "deepseek"
        case .apple: "apple"
        case .appleIntelligence: "apple_intelligence"
        }
    }

    init?(backendID: String) {
        switch backendID {
        case "ollama": self = .ollama
        case "openai": self = .openAI
        case "anthropic": self = .anthropic
        case "deepseek": self = .deepSeek
        case "apple": self = .apple
        case "apple_intelligence": self = .appleIntelligence
        default: return nil
        }
    }
}

enum DistributionMode: String {
    case direct
    case appStore

    static var current: DistributionMode {
        let rawValue = Bundle.main.object(forInfoDictionaryKey: "DistributionMode") as? String
        return rawValue == "app-store" ? .appStore : .direct
    }

    var title: String {
        switch self {
        case .direct: "Direct Download"
        case .appStore: "App Store"
        }
    }

    var titleResource: LocalizedStringResource {
        switch self {
        case .direct: "Direct Download"
        case .appStore: "App Store"
        }
    }

    var canManageOllama: Bool { self == .direct }
    var canGenerateFrenchNSI: Bool { self == .direct }
}

struct OllamaState: Equatable {
    var installed = false
    var running = false
    var command: String?
    var message = "Not checked"

    var messageResource: LocalizedStringResource {
        LocalizedStringResource(stringLiteral: message)
    }
}


struct MLXDownloadInfo: Equatable {
    let model: String
    let downloadBytes: Int
    let cached: Bool
    let revision: String?

    var isValid: Bool {
        guard !model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && (0...9_007_199_254_740_991).contains(downloadBytes)
            && (!cached || downloadBytes == 0) else { return false }
        if let revision {
            return (40...64).contains(revision.utf8.count)
                && revision.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
        }
        return cached
    }
}


enum MLXModelAccessPolicy {
    static func issue(model: String, distributionMode: DistributionMode) -> LocalizedStringResource? {
        guard distributionMode == .appStore else { return nil }
        let parts = model.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "/", omittingEmptySubsequences: false)
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        guard parts.count == 2, parts.allSatisfy({
            !$0.isEmpty && $0 != "." && $0 != ".." && $0.unicodeScalars.allSatisfy(allowed.contains)
        }) else {
            return "In the App Store version, enter a Hugging Face model ID such as owner/model. Models are prepared in Keldin's own storage; external model folders are not supported."
        }
        return nil
    }
}

enum MLXSetupPolicy {
    static func requiresSetup(
        provider: AIProvider,
        model: String,
        preparedModels: Set<String>,
        usesAI: Bool,
        dryRun: Bool
    ) -> Bool {
        guard provider == .apple, usesAI, !dryRun else { return false }
        let model = model.trimmingCharacters(in: .whitespacesAndNewlines)
        return !model.isEmpty && !preparedModels.contains(model)
    }
}

struct MLXRecoveryState {
    private(set) var needsSetupAfterGeneration = false

    mutating func beginGeneration() {
        needsSetupAfterGeneration = false
    }

    mutating func requestSetup() {
        needsSetupAfterGeneration = true
    }

    mutating func cancel() {
        needsSetupAfterGeneration = false
    }

    mutating func consumeSetupRequest() -> Bool {
        defer { needsSetupAfterGeneration = false }
        return needsSetupAfterGeneration
    }
}
