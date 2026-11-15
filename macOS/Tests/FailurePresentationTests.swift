import Foundation
import XCTest
@testable import Keldin

final class FailurePresentationTests: XCTestCase {
    func testCachedMLXSetupProgressUsesSelectedLanguage() {
        let message = "Keldin is preparing the selected local model."
        XCTAssertEqual(GenerationPresentation.progress(message, language: "en"), message)
        XCTAssertEqual(
            GenerationPresentation.progress(message, language: "fr"),
            "Keldin prépare le modèle local sélectionné."
        )
    }

    func testLocalMemoryRefusalUsesSelectedLanguageNotProviderDetails() {
        let raw = "PRIVATE_RESOURCE_DETAILS"
        let english = "Local generation couldn't start within the memory checks. Choose a smaller model, close memory-heavy apps, or use a remote provider."
        let french = "La création locale n’a pas pu démarrer après les vérifications de mémoire. Choisissez un modèle plus petit, fermez les apps gourmandes en mémoire ou utilisez un moteur distant."
        XCTAssertEqual(GenerationPresentation.error(raw, code: "local_memory_unavailable", language: "en"), english)
        XCTAssertEqual(GenerationPresentation.error(raw, code: "local_memory_unavailable", language: "fr"), french)
        XCTAssertEqual(GenerationPresentation.error(raw, code: "generation_failed", language: "en"), raw)
        XCTAssertEqual(GenerationPresentation.failureKind(for: raw, code: "local_memory_unavailable"), .generationFailed)
    }

    func testSavedFailureDetailsFollowTheInterfaceLanguage() {
        for kind in GenerationFailureKind.allCases {
            for resource in [kind.stageResource, kind.detailResource] {
                let english = InterfaceText.resolve(resource, language: "en")
                let french = InterfaceText.resolve(resource, language: "fr")
                XCTAssertFalse(english.isEmpty)
                XCTAssertFalse(french.isEmpty)
                XCTAssertNotEqual(english, french)
            }
        }
        let resource: LocalizedStringResource = "Failure details were not recorded for this run."
        XCTAssertEqual(InterfaceText.resolve(resource, language: "fr"), "Les détails de l’échec n’ont pas été enregistrés pour cette tentative.")
    }

    func testFrenchContextRefusalUsesSelectedLanguageAndOffersRecovery() {
        let raw = "Capacité du contexte non vérifiée ou insuffisante pour cet exercice."
        let code = "french_model_context_unavailable"
        XCTAssertEqual(
            GenerationPresentation.error(raw, code: code, language: "en"),
            "Keldin couldn't confirm that the full exercise fits the model's context window. Try a different model or provider in Settings. No paper was saved."
        )
        XCTAssertEqual(
            GenerationPresentation.error(raw, code: code, language: "fr"),
            "Keldin n’a pas pu vérifier que l’exercice entier tient dans la fenêtre de contexte du modèle. Essayez un autre modèle ou fournisseur dans Réglages. Aucun sujet n’a été enregistré."
        )
        XCTAssertEqual(GenerationPresentation.error(raw, code: "french_generation_failed", language: "en"), raw)
        XCTAssertEqual(GenerationPresentation.failureKind(for: raw, code: code), .frenchPaperFailed)
    }

    func testFailureKindsUseTheExistingNarrowQualityClassification() {
        let quality = "question 01 failed independent solution reconciliation: answer mismatch"
        XCTAssertEqual(GenerationPresentation.failureKind(for: quality, code: "generation_failed"), .qualityChecksFailed)
        XCTAssertEqual(GenerationPresentation.failureKind(for: quality, code: "provider_error"), .generationFailed)
        XCTAssertEqual(GenerationPresentation.failureKind(for: "Provider unavailable\n" + quality, code: "generation_failed"), .generationFailed)
        XCTAssertEqual(GenerationPresentation.failureKind(for: "L'exercice 1 reste mal structuré après deux tentatives : invalid shape", code: "french_generation_failed"), .qualityChecksFailed)
        XCTAssertEqual(GenerationPresentation.failureKind(for: "Connection failed", code: "french_generation_failed"), .frenchPaperFailed)
        XCTAssertEqual(GenerationPresentation.failureKind(for: "Private details", code: "mlx_setup_required"), .modelSetupRequired)
        XCTAssertEqual(GenerationPresentation.failureKind(for: "Private details", code: nil), .generationFailed)
    }

    func testFrenchAuthoredShapeFailureUsesTheLocalizedQualityMessage() {
        let code = "french_authoring_structure"
        let message = "Le modèle n'a pas produit un exercice utilisable."
        let existingQuality = "L'exercice 1 reste mal structuré après deux tentatives : invalid shape"
        for language in ["en", "fr"] {
            XCTAssertEqual(
                GenerationPresentation.error(message, code: code, language: language),
                GenerationPresentation.error(existingQuality, code: "french_generation_failed", language: language)
            )
        }
        XCTAssertEqual(GenerationPresentation.failureKind(for: message, code: code), .qualityChecksFailed)
    }

    @MainActor
    func testBackendFailureKindReachesOwnedHistoryWithoutSavingTheRawMessage() throws {
        let defaults = isolatedDefaults()
        defaults.set(true, forKey: AppStorageKey.hasSeenWelcome)
        defaults.set(false, forKey: AppStorageKey.notificationsEnabled)
        let backend = ControlledRunBackend()
        let application = isolatedApplication(defaults: defaults, backend: backend)
        application.setDryRun(true)
        application.generate()
        let request = try XCTUnwrap(backend.requests.first)
        let raw = "question 01 failed independent solution reconciliation: PRIVATE_MODEL_DRAFT"
        request.onEvent(.error(message: raw, code: "generation_failed"))
        request.onFinish(.success(1))
        let failed = try XCTUnwrap(application.recentDocumentStore.records.first)
        XCTAssertEqual(failed.state, .failed)
        XCTAssertEqual(failed.failureKind, .qualityChecksFailed)
        XCTAssertEqual(application.generationCoordinator.status, raw)
        application.generate()
        XCTAssertEqual(application.recentDocumentStore.records.first { $0.id == failed.id }?.failureKind, .qualityChecksFailed)
        backend.requests.last?.onFinish(.success(1))
    }
}
