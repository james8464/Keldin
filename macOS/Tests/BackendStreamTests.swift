import Foundation
import Combine
import XCTest
@testable import Keldin

final class BackendStreamTests: XCTestCase {
    private func layoutEvent(page: Int = 2, model: String = "fixture:latest") throws -> BackendEvent {
        let digest = String(repeating: "a", count: 64)
        return try BackendEvent(jsonLine: """
        {"type":"custom_page_layout","role":"question-paper","sha256":"\(digest)","page":\(page),"model":"\(model)","layout":{"heading":"Practice","columns":1,"question_markers":["1"],"response_space":["box"],"figures":["diagram"]}}
        """)
    }

    func testPageLayoutRejectsInvalidMetadata() throws {
        XCTAssertThrowsError(try layoutEvent(page: 81))
        XCTAssertThrowsError(try layoutEvent(model: "https://example.com"))
        guard case let .customPageLayout(value) = try layoutEvent() else {
            return XCTFail("Expected a page layout")
        }
        XCTAssertEqual(value.layout.questionMarkers, ["1"])
        XCTAssertEqual(value.layout.responseSpace, ["box"])
    }

    @MainActor
    func testPageLayoutBindsSourcePageAndModelAndReleasesAccess() async throws {
        let selection = CustomAssessmentSelection(
            role: .questionPaper, url: URL(fileURLWithPath: "/tmp/Keldin Layout Test.pdf")
        )
        let digest = String(repeating: "a", count: 64)
        let metadata = CustomAssessmentSourceMetadata(
            role: .questionPaper, sha256: digest, pageCount: 2, pagesWithoutText: [2]
        )
        let valid = try layoutEvent()
        let expectedArguments = [
            "inspect-custom-page-layout", "--source", "question-paper", selection.url.path,
            "--sha256", digest, "--page", "2", "--model", "fixture:latest",
        ]
        let fixtures: [([BackendEvent], CustomAssessmentInspectionError?)] = [
            ([valid], nil),
            ([valid, valid], .invalidResponse),
            ([try layoutEvent(page: 1)], .invalidResponse),
            ([try layoutEvent(model: "other:latest")], .invalidResponse),
            ([valid, .error(message: "private stderr")], .invalidResponse),
            ([.error(message: "Not enough memory.", code: "local_memory_unavailable")], .rejected("Not enough memory.")),
        ]
        for (events, expectedError) in fixtures {
            var acquired: [URL] = []
            var released: [URL] = []
            let backend = CustomInspectionFixture(expectedArguments: expectedArguments, events: events)
            do {
                let result = try await CustomAssessmentInspection.observePage(
                    2, of: selection, verified: metadata, model: "fixture:latest", backend: backend,
                    startAccess: { acquired.append($0); return true },
                    stopAccess: { released.append($0) }
                )
                XCTAssertNil(expectedError)
                XCTAssertEqual(BackendEvent.customPageLayout(result), valid)
            } catch {
                XCTAssertEqual(error as? CustomAssessmentInspectionError, expectedError)
            }
            XCTAssertEqual(acquired, [selection.url])
            XCTAssertEqual(released, acquired)
        }
    }

    @MainActor
    func testCustomInspectionReleasesScopedAccessAndRejectsErrorsAfterResult() async throws {
        let selections = (1...3).map {
            CustomAssessmentSelection(role: .questionPaper, url: URL(fileURLWithPath: "/tmp/Keldin Sample \($0).pdf"))
        }
        let sources = ["a", "b", "c"].map {
            CustomAssessmentSourceMetadata(role: .questionPaper, sha256: String(repeating: $0, count: 64), pageCount: 2, pagesWithoutText: [2])
        }
        let expectedArguments = ["inspect-custom-assessment"] + selections.flatMap {
            ["--source", "question-paper", $0.url.path]
        }
        for shouldFail in [false, true] {
            var acquired: [URL] = []
            var released: [URL] = []
            let events: [BackendEvent] = [.customAssessmentSources(sources)] + (shouldFail ? [
                .error(message: "private path in unexpected stderr"),
            ] : [])
            let backend = CustomInspectionFixture(expectedArguments: expectedArguments, events: events)
            do {
                let result = try await CustomAssessmentInspection.inspect(selections, backend: backend, startAccess: {
                    acquired.append($0)
                    return true
                }, stopAccess: { released.append($0) })
                XCTAssertFalse(shouldFail)
                XCTAssertEqual(result, sources)
            } catch {
                XCTAssertTrue(shouldFail)
                XCTAssertEqual(error as? CustomAssessmentInspectionError, .invalidResponse)
            }
            XCTAssertEqual(acquired, selections.map(\.url))
            XCTAssertEqual(released, Array(acquired.reversed()))
        }
    }

    func testCustomInspectionDecodesOnlyBoundedSourceMetadata() throws {
        let hashes = ["a", "b", "c"].map { String(repeating: $0, count: 64) }
        let sources = hashes.map { hash in
            """
            {"role":"question-paper","sha256":"\(hash)","page_count":2,"pages_without_text":[2]}
            """
        }.joined(separator: ",")
        let json = """
        {"type":"custom_assessment_sources","sources":[\(sources)]}
        """
        guard case let .customAssessmentSources(result) = try BackendEvent(jsonLine: json) else {
            return XCTFail("Expected custom assessment sources")
        }
        XCTAssertEqual(result.map(\.sha256), hashes)
        XCTAssertEqual(result.map(\.pagesWithoutText), [[2], [2], [2]])
        XCTAssertNoThrow(try BackendEvent(jsonLine: json.replacingOccurrences(of: "[2]", with: "[1,2]")))
        for malformed in [
            json.replacingOccurrences(of: "[2]", with: "[3]"),
            json.replacingOccurrences(of: "[2]", with: "[2,2]"),
            json.replacingOccurrences(of: hashes[1], with: hashes[0]),
            json.replacingOccurrences(of: "question-paper", with: "syllabus"),
        ] {
            XCTAssertThrowsError(try BackendEvent(jsonLine: malformed))
        }
    }

    func testFrenchSavedCancellationDecodesOnlyAnExactBundleName() throws {
        let bundle = "nsi-2027-v36-42-0123456789ab"
        func decode(_ name: String, code: String = "cancelled") throws -> BackendEvent {
            let data = try JSONEncoder().encode([
                "type": "error", "message": "Cancelled", "code": code, "retained_bundle": name,
            ])
            return try BackendEvent(jsonLine: String(decoding: data, as: UTF8.self))
        }
        XCTAssertEqual(try decode(bundle), .cancelledAfterSave(message: "Cancelled", bundle: bundle))
        for invalid in ["../\(bundle)", "/\(bundle)", "\(bundle)/x", "\(bundle)\n", "nsi-2027-v36-42-not-a-digest"] {
            XCTAssertEqual(try decode(invalid), .error(message: "Cancelled", code: "cancelled"))
        }
        XCTAssertEqual(try decode(bundle, code: "failed"), .error(message: "Cancelled", code: "failed"))
    }

    @MainActor
    func testCollectionFailureReachesTheRefreshErrorPresentation() async throws {
        let application = isolatedApplication(backend: try fixtureClient("exit 7"))
        application.refreshOllama()
        let finished = expectation(description: "Refresh finishes")
        let subscription = application.$isRefreshingOllama.filter { !$0 }.prefix(1).sink { _ in finished.fulfill() }
        await fulfillment(of: [finished], timeout: 3)
        subscription.cancel()
        XCTAssertTrue(application.showError)
        XCTAssertTrue(application.errorMessage.contains("7"))
    }

    func testCollectionReportsMalformedJSONAndInvalidUTF8WithoutDroppingValidEvents() async throws {
        for body in [
            #"printf '%s\n' 'not JSON' '{"type":"done","message":"Valid event"}'"#,
            #"printf '\377\n'; printf '%s' '{"type":"done","message":"Valid event"}'"#,
        ] {
            let client = try fixtureClient(body)
            let events = try await client.collect(arguments: [])
            XCTAssertEqual(events.count, 2)
            guard case .error = events.first else { return XCTFail("Malformed output must be reported") }
            XCTAssertEqual(events.last, .done(message: "Valid event"))
        }
    }

    func testCollectionReportsNonzeroExitWithEmptyStderr() async throws {
        let events = try await fixtureClient("exit 7").collect(arguments: [])
        XCTAssertEqual(events.count, 1)
        guard case let .error(message, _) = events.first else { return XCTFail("Exit failure must be reported") }
        XCTAssertTrue(message.contains("7"))
    }

    @MainActor
    func testStreamingPreservesStructuredFailureWhenHelperWritesStderr() async throws {
        let code = "french_model_context_unavailable"
        let message = "Context refused"
        let terminal = #"{"type":"error","message":"Context refused","code":"french_model_context_unavailable"}"#
        for (output, expected) in [
            (terminal, [.error(message: message, code: code)]),
            ("", [.error(message: "Fixture stderr warning")]),
        ] as [(String, [BackendEvent])] {
            let client = try fixtureClient("printf '%s' '\(output)'; printf '%s' 'Fixture stderr warning' >&2; exit 7")
            let finished = expectation(description: "Stream exits")
            var events: [BackendEvent] = []
            _ = try client.run(arguments: [], onEvent: { events.append($0) }, onFinish: { result in
                XCTAssertEqual(try? result.get(), 7)
                finished.fulfill()
            })
            await fulfillment(of: [finished], timeout: 3)
            XCTAssertEqual(events, expected)
        }
    }

    func testCollectionPreservesExplicitErrorsAndUnicodeEOFEvents() async throws {
        let detail = #"{"type":"error","message":"Exact backend detail","code":"fixture"}"#
        let explicit = try await fixtureClient("printf '%s' '\(detail)'; exit 9").collect(arguments: [])
        XCTAssertEqual(explicit, [.error(message: "Exact backend detail", code: "fixture")])
        let valid = try await fixtureClient(#"printf '\n\r\n'; printf '%s\r\n' '{"type":"progress","stage":"fixture","message":"Créée ☀️","progress":0.5}'; printf '%s' '{"type":"done","message":"Terminée"}'"#).collect(arguments: [])
        XCTAssertEqual(valid, [.progress(stage: "fixture", message: "Créée ☀️", progress: 0.5), .done(message: "Terminée")])
        let stderr = try await fixtureClient("printf '%s' 'Exact diagnostic' >&2; exit 8").collect(arguments: [])
        XCTAssertEqual(stderr, [.error(message: "Exact diagnostic")])
    }

    func testImplicitDevelopmentRootWorksWithAnUnrelatedDeepBundle() throws {
        let environment = ProcessInfo.processInfo.environment
        try XCTSkipIf(KeldinMigration.environmentValue("KELDIN_ROOT", environment: environment) != nil, "This fixture requires no development-root override")
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }
        let deepBundle = (0..<12).reduce(root) { path, index in path.appendingPathComponent("level\(index)") }.appendingPathComponent("Missing.app")
        try FileManager.default.createDirectory(at: deepBundle, withIntermediateDirectories: true)
        let client = BackendClient(bundleURL: deepBundle, distributionMode: .direct)
        let launch = try client.launchConfiguration(arguments: ["ollama-status"])
        let repository = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        XCTAssertEqual(launch.workingDirectory.standardizedFileURL, repository.standardizedFileURL)
        XCTAssertEqual(launch.arguments, [repository.appendingPathComponent("bridge.py").path, "ollama-status"])
        XCTAssertThrowsError(try BackendClient(bundleURL: deepBundle, distributionMode: .appStore).launchConfiguration(arguments: []))
    }

    private func fixtureClient(_ body: String) throws -> BackendClient {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("KeldinBackendFixture-\(UUID().uuidString)")
        addTeardownBlock { try? FileManager.default.removeItem(at: root) }
        let executable = root.appendingPathComponent("Contents/Resources/KeldinBackend/KeldinBackend")
        try FileManager.default.createDirectory(at: executable.deletingLastPathComponent(), withIntermediateDirectories: true)
        try ("#!/bin/sh\n" + body + "\n").write(to: executable, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)
        return BackendClient(bundleURL: root, distributionMode: .appStore)
    }

    func testFrenchEventSurvivesEveryPossibleByteSplit() throws {
        let line = #"{"type":"progress","stage":"render","message":"Épreuve créée à Noël ☀️","progress":0.5}"#
        let data = Data((line + "\n").utf8)
        for split in 0...data.count {
            var buffer = BackendEventLineBuffer()
            let lines = buffer.append(Data(data.prefix(split)))
                + buffer.append(Data(data.dropFirst(split)))
            XCTAssertEqual(lines, [line], "Byte split \(split)")
            XCTAssertEqual(buffer.finish(), "")
            if let received = lines.first {
                XCTAssertEqual(
                    try BackendEvent(jsonLine: received),
                    .progress(stage: "render", message: "Épreuve créée à Noël ☀️", progress: 0.5)
                )
            }
        }
    }

    func testSeveralLinesAndFinalUnterminatedEventKeepTheirOrder() {
        var buffer = BackendEventLineBuffer()
        XCTAssertEqual(buffer.append(Data("première\n\ndeuxième\nfin é".utf8)), ["première", "", "deuxième"])
        XCTAssertEqual(buffer.finish(), "fin é")
        XCTAssertEqual(buffer.finish(), "")
    }

    func testOneByteChunksPreserveUnicodeAndFinalLine() {
        var buffer = BackendEventLineBuffer()
        let source = "créée\n完了\n🌞"
        let lines = Data(source.utf8).flatMap { buffer.append(Data([$0])) }
        XCTAssertEqual(lines, ["créée", "完了"])
        XCTAssertEqual(buffer.finish(), "🌞")
    }

    func testInvalidUTF8IsRejectedInsteadOfDroppedOrRepairedInsideJSON() {
        var buffer = BackendEventLineBuffer()
        var data = Data(#"{"type":"done","message":""#.utf8)
        data.append(0xFF)
        data.append(contentsOf: Data("\"}\n".utf8))
        let lines = buffer.append(data)
        XCTAssertEqual(lines.count, 1)
        XCTAssertThrowsError(try BackendEvent(jsonLine: lines[0]))
        XCTAssertEqual(buffer.finish(), "")

        XCTAssertEqual(buffer.append(Data([0xFF])), [])
        XCTAssertThrowsError(try BackendEvent(jsonLine: buffer.finish()))
    }
}

private struct CustomInspectionFixture: BackendRunning {
    let expectedArguments: [String]
    let events: [BackendEvent]

    func collect(arguments: [String]) async throws -> [BackendEvent] {
        XCTAssertEqual(arguments, expectedArguments)
        return events
    }

    func run(
        arguments: [String], environment: [String: String],
        onEvent: @escaping @Sendable @MainActor (BackendEvent) -> Void,
        onFinish: @escaping @Sendable @MainActor (Result<Int32, Error>) -> Void
    ) throws -> Process {
        XCTFail("Inspection must not launch a generation run")
        throw CustomAssessmentInspectionError.invalidResponse
    }
}
