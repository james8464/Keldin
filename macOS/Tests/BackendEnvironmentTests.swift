import XCTest
@testable import Keldin

final class BackendEnvironmentTests: XCTestCase {
    func testLocalProviderUsesOnlyLocalSettings() {
        let environment = BackendEnvironment.make(
            provider: .ollama,
            distributionMode: .direct,
            parallelLocalReviews: true,
            parallelMLXGeneration: false,
            hostedAPIKey: "unused-key"
        )

        XCTAssertEqual(environment["KELDIN_PARALLEL_LOCAL_REVIEWS"], "1")
        XCTAssertEqual(environment["KELDIN_PARALLEL_MLX_GENERATION"], "0")
        XCTAssertNil(environment["KELDIN_API_KEY"])
        XCTAssertNil(environment["HF_HOME"])
    }

    func testHostedProviderUsesTrimmedKeyAndRunMetadata() {
        let environment = BackendEnvironment.make(
            provider: .openAI,
            distributionMode: .direct,
            parallelLocalReviews: false,
            parallelMLXGeneration: false,
            hostedAPIKey: "  key-123  ",
            runMetadata: ["KELDIN_JOB_ID": "job-1"]
        )

        XCTAssertEqual(environment["KELDIN_API_KEY"], "key-123")
        XCTAssertEqual(environment["KELDIN_JOB_ID"], "job-1")
        XCTAssertEqual(environment["KELDIN_PARALLEL_LOCAL_REVIEWS"], "0")
    }

    func testAppleProviderUsesManagedCacheFolder() {
        let environment = BackendEnvironment.make(
            provider: .apple,
            distributionMode: .direct,
            parallelLocalReviews: false,
            parallelMLXGeneration: false,
            hostedAPIKey: ""
        )

        XCTAssertEqual(
            environment["HF_HOME"],
            AppDefaults.mlxCacheFolder().path
        )
        XCTAssertNil(environment["KELDIN_API_KEY"])
    }

    func testAppleIntelligenceUsesDistributionHelperPath() {
        let environment = BackendEnvironment.make(
            provider: .appleIntelligence,
            distributionMode: .direct,
            parallelLocalReviews: false,
            parallelMLXGeneration: false,
            hostedAPIKey: ""
        )

        XCTAssertEqual(
            environment["KELDIN_APPLE_INTELLIGENCE_HELPER"],
            AppleIntelligenceAvailability.helperURL(distributionMode: .direct).path
        )
    }
}
