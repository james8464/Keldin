// Assemble the process environment shared by generation and French runs.

import Foundation

enum BackendEnvironment {
    /// Keys understood by the Python backend for a single run.
    ///
    /// Callers supply run metadata (job identity, timestamps) so this builder
    /// stays deterministic and testable.
    static func make(
        provider: AIProvider,
        distributionMode: DistributionMode,
        parallelLocalReviews: Bool,
        parallelMLXGeneration: Bool,
        hostedAPIKey: String,
        runMetadata: [String: String] = [:]
    ) -> [String: String] {
        var environment = [
            "KELDIN_PARALLEL_LOCAL_REVIEWS": parallelLocalReviews ? "1" : "0",
            "KELDIN_PARALLEL_MLX_GENERATION": parallelMLXGeneration ? "1" : "0",
        ]
        environment.merge(runMetadata) { _, supplied in supplied }
        switch provider {
        case .ollama:
            break
        case .openAI, .anthropic, .deepSeek:
            environment["KELDIN_API_KEY"] = hostedAPIKey.trimmingCharacters(
                in: .whitespacesAndNewlines
            )
        case .apple:
            environment["HF_HOME"] = AppDefaults.mlxCacheFolder().path
        case .appleIntelligence:
            environment["KELDIN_APPLE_INTELLIGENCE_HELPER"] =
                AppleIntelligenceAvailability.helperURL(
                    distributionMode: distributionMode
                ).path
        }
        return environment
    }
}
