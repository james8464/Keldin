// Decode backend records and represent the selections shown by the app.

// Generation progress, estimates and saved quality evidence.

import Foundation

struct ProgressEntry: Identifiable, Equatable {
    let id = UUID()
    let date = Date()
    let stage: String?
    let message: String
}

struct EstimateFactor: Identifiable, Equatable {
    let id = UUID()
    let title: String
    let detail: String
    let impact: Double
}

struct GenerationEstimate: Equatable {
    let startedAt: Date
    var totalSeconds: TimeInterval
    var remainingSeconds: TimeInterval
    var confidence: Double
    var factors: [EstimateFactor]
    var lastUpdatedAt: Date? = nil
    var lastObservedProgress: Double? = nil
    var elapsedSeconds: TimeInterval? = nil
    var hasDurationEstimate = true

    var etaDate: Date {
        Date().addingTimeInterval(max(0, remainingSeconds))
    }

    var remainingText: String {
        guard hasDurationEstimate else {
            return String(localized: "Time remaining is not yet known.")
        }
        guard remainingSeconds > 0 else {
            return String(localized: "Taking longer than estimated")
        }
        return Self.formatDuration(max(1, remainingSeconds))
    }

    static func formatDuration(_ seconds: TimeInterval) -> String {
        let clamped = max(0, Int(seconds.rounded()))
        if clamped < 60 {
            return "\(clamped)s"
        }
        let minutes = clamped / 60
        let remainder = clamped % 60
        return remainder == 0 ? "\(minutes)m" : "\(minutes)m \(remainder)s"
    }
}


enum SavedGenerationMode: String, Equatable {
    case preview = "Preview"
    case live = "Live"
    case unknown = "Unknown"
}

struct SavedPackageIdentity: Equatable {
    let subject: String?
    let paper: String?
    let seed: Int?
    let jobID: String?
    let generatorID: String?
    let generatorVersion: String?
    let formID: String?
}

enum AuthoringProvenanceKind: Equatable {
    case reviewedFixedOnly
    case aiAuthoredOnly
    case mixed
    case unreviewed
    case unknown
}

struct AuthoringProvenanceSummary: Equatable {
    let kind: AuthoringProvenanceKind
    let reviewedFixedItems: Int?
    let aiAuthoredItems: Int?
    let aiAuthoredStemItems: Int?
    let unreviewedItems: Int?
    let unknownItems: Int?

    static let unknown = AuthoringProvenanceSummary(
        kind: .unknown,
        reviewedFixedItems: nil,
        aiAuthoredItems: nil,
        aiAuthoredStemItems: nil,
        unreviewedItems: nil,
        unknownItems: nil
    )
}

enum GenerationQualityState: Equatable {
    case passed
    case pending
    case preview
    case atCreation
    case unknown
    case insufficient

    var title: String {
        switch self {
        case .passed: "Passed"
        case .pending: "Pending"
        case .preview: "Preview"
        case .atCreation: "At creation"
        case .unknown: "Unknown"
        case .insufficient: "Insufficient"
        }
    }
}

struct GenerationQualityPresentation: Equatable {
    let originalityState: GenerationQualityState
    let originalityDetail: String
    let referenceDemandState: GenerationQualityState
    let referenceDemandDetail: String
    let pathEvidenceState: GenerationQualityState
    let pathEvidenceDetail: String
    let diagnosticLines: [String]
}

struct GenerationQualityReport: Equatable {
    let identity: SavedPackageIdentity
    let savedMode: SavedGenerationMode
    let itemCount: Int
    let fingerprintsVerified: Bool
    let historicComparisons: Int
    let noveltyPassed: Bool?
    let crossGenerationPolicy: String?
    let withinPaperPassed: Bool?
    let historicalOverlap: Bool?
    let nearestSimilarity: Double?
    let pdfCount: Int
    let engineeringValidated: Bool?
    let visuallyCalibrated: Bool?
    let empiricallyCalibrated: Bool?
    let referenceDemandPassed: Bool?
    let referenceDemandItems: Int
    let referenceDemandDocuments: Int
    let referenceDemandMaxDistance: Double?
    let referenceDemandExtractionCoverage: Double?
    let referenceDemandFailedChecks: [String]?
    let difficultyReviewedItems: Int
    let difficultyApprovedItems: Int?
    let difficultyReviewCoverage: Double?
    let difficultyReasoningFitItems: Int?
    let difficultyContextFitItems: Int?
    let difficultyShortcutFitItems: Int?
    let candidatePathEvidencePassed: Bool?
    let referenceEvidenceState: String?
    let pathEvidenceState: String?
    let candidatePathCount: Int?
    let candidateMarkRange: [Int]?
    let printedMarks: Int?
    let evidenceGaps: [String]
    let authoringProvenance: AuthoringProvenanceSummary

    static func load(from url: URL) -> GenerationQualityReport? {
        guard let data = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let evidence = root["evidence"] as? [String: Any],
              let assessment = evidence["assessment_validation"] as? [String: Any],
              let novelty = evidence["novelty_validation"] as? [String: Any],
              let outputs = root["outputs"] as? [String: Any] else {
            return nil
        }
        let nearest = novelty["nearest_match"] as? [String: Any]
        let request = root["request"] as? [String: Any]
        let generator = root["generator"] as? [String: Any]
        let qualification = evidence["qualification_levels"] as? [String: Any]
        let referenceDemand = assessment["reference_demand"] as? [String: Any]
        let distances = referenceDemand?["gated_distances"] as? [String: Double]
        let itemReview = referenceDemand?["item_review_evidence"] as? [String: Any]
        let pathEvidence = assessment["path_evidence"] as? [String: Any]
            ?? referenceDemand?["path_evidence"] as? [String: Any]
        let topicEvidence = referenceDemand?["topic_evidence"] as? [String: Any]
        let assessmentItemCount = assessment["item_count"] as? Int ?? 0
        let mode: SavedGenerationMode
        if let preview = request?["preview_mode"] as? Bool {
            mode = preview ? .preview : .live
        } else {
            mode = .unknown
        }
        let pdfCount = outputs.values.compactMap { value -> [String: Any]? in
            value as? [String: Any]
        }.filter { $0["pdf_validation"] is [String: Any] }.count
        return GenerationQualityReport(
            identity: SavedPackageIdentity(
                subject: Self.nonEmpty(request?["subject"] as? String),
                paper: Self.nonEmpty(request?["paper"] as? String),
                seed: request?["seed"] as? Int,
                jobID: Self.nonEmpty(root["job_id"] as? String),
                generatorID: Self.nonEmpty(generator?["id"] as? String),
                generatorVersion: Self.nonEmpty(generator?["version"] as? String),
                formID: Self.nonEmpty(assessment["form_id"] as? String)
            ),
            savedMode: mode,
            itemCount: assessmentItemCount,
            fingerprintsVerified: assessment["fingerprints_verified"] as? Bool ?? false,
            historicComparisons: novelty["historic_comparisons"] as? Int ?? 0,
            noveltyPassed: novelty["passed"] as? Bool,
            crossGenerationPolicy: novelty["cross_generation_policy"] as? String,
            withinPaperPassed: novelty["within_paper_passed"] as? Bool,
            historicalOverlap: novelty["historical_overlap"] as? Bool,
            nearestSimilarity: nearest?["similarity"] as? Double,
            pdfCount: pdfCount,
            engineeringValidated: qualification?["engineering_validated"] as? Bool,
            visuallyCalibrated: qualification?["visually_calibrated"] as? Bool,
            empiricallyCalibrated: qualification?["empirically_calibrated"] as? Bool,
            referenceDemandPassed: referenceDemand?["passed"] as? Bool,
            referenceDemandItems: referenceDemand?["items_checked"] as? Int ?? 0,
            referenceDemandDocuments: referenceDemand?["source_document_count"] as? Int ?? 0,
            referenceDemandMaxDistance: distances?.values.max(),
            referenceDemandExtractionCoverage: referenceDemand?["extraction_coverage"] as? Double,
            referenceDemandFailedChecks: referenceDemand?["failed_checks"] as? [String],
            difficultyReviewedItems: itemReview?["reviewed_items"] as? Int ?? 0,
            difficultyApprovedItems: itemReview?["approved_items"] as? Int,
            difficultyReviewCoverage: itemReview?["coverage"] as? Double,
            difficultyReasoningFitItems: itemReview?["reasoning_range_fit"] as? Int,
            difficultyContextFitItems: itemReview?["context_fit"] as? Int,
            difficultyShortcutFitItems: itemReview?["shortcut_resistant"] as? Int,
            candidatePathEvidencePassed: pathEvidence?["passed"] as? Bool,
            referenceEvidenceState: referenceDemand?["evidence_state"] as? String,
            pathEvidenceState: pathEvidence?["evidence_state"] as? String,
            candidatePathCount: pathEvidence?["path_count"] as? Int,
            candidateMarkRange: pathEvidence?["candidate_mark_range"] as? [Int],
            printedMarks: pathEvidence?["printed_marks"] as? Int,
            evidenceGaps: topicEvidence?["gaps"] as? [String] ?? [],
            authoringProvenance: Self.decodeAuthoringProvenance(
                assessment["authoring_provenance"] as? [String: Any],
                expectedItems: assessmentItemCount
            )
        )
    }

    private static func decodeAuthoringProvenance(
        _ value: [String: Any]?,
        expectedItems: Int
    ) -> AuthoringProvenanceSummary {
        guard let value,
              value["schema_version"] as? Int == 1,
              let items = value["items"] as? Int,
              let fixed = value["reviewed_fixed_items"] as? Int,
              let authored = value["ai_authored_items"] as? Int,
              let stems = value["ai_authored_stem_items"] as? Int,
              let unreviewed = value["unreviewed_or_builtin_items"] as? Int,
              let unknown = value["unknown_items"] as? Int,
              items >= 0,
              items == expectedItems
        else { return .unknown }
        // Consume the declared total so malformed counts cannot overflow a sum.
        var remaining = items
        for count in [fixed, authored, stems, unreviewed, unknown] {
            guard count >= 0, count <= remaining else { return .unknown }
            remaining -= count
        }
        guard remaining == 0 else { return .unknown }
        let kind: AuthoringProvenanceKind
        if unknown > 0 {
            kind = .unknown
        } else if fixed == items {
            kind = .reviewedFixedOnly
        } else if authored + stems == items {
            kind = .aiAuthoredOnly
        } else if unreviewed == items {
            kind = .unreviewed
        } else {
            kind = .mixed
        }
        return AuthoringProvenanceSummary(
            kind: kind,
            reviewedFixedItems: fixed,
            aiAuthoredItems: authored,
            aiAuthoredStemItems: stems,
            unreviewedItems: unreviewed,
            unknownItems: unknown
        )
    }

    private static func nonEmpty(_ value: String?) -> String? {
        guard let value = value?.trimmingCharacters(in: .whitespacesAndNewlines),
              !value.isEmpty else { return nil }
        return value
    }
}

enum GenerationQualityPolicy {
    static func presentation(
        for report: GenerationQualityReport?, locale: Locale = .current
    ) -> GenerationQualityPresentation {
        func text(_ resource: LocalizedStringResource) -> String {
            String(localized: InterfaceText.localizedResource(resource, locale: locale))
        }
        guard let report else {
            return GenerationQualityPresentation(
                originalityState: .atCreation,
                originalityDetail: text("Originality evidence is created with a saved package."),
                referenceDemandState: .atCreation,
                referenceDemandDetail: text("Reference-demand evidence is created with a saved package."),
                pathEvidenceState: .unknown,
                pathEvidenceDetail: text("Candidate-path evidence is not available."),
                diagnosticLines: ["Saved package evidence: None"]
            )
        }
        let originalityState: GenerationQualityState
        let originalityDetail: String
        switch report.savedMode {
        case .preview:
            originalityState = .preview
            originalityDetail = text("Preview history comparison is skipped; authorship and originality are not reviewed.")
        case .live where report.crossGenerationPolicy == "repeat-practice-v1":
            originalityState = .unknown
            originalityDetail = report.withinPaperPassed == true
                ? text("Repeat practice allows overlap with earlier papers. Questions within this paper were checked for duplicates.")
                : text("Repeat practice allows overlap with earlier papers. Duplicate checks within this paper are incomplete.")
        case .live where report.crossGenerationPolicy != nil && report.crossGenerationPolicy != "strict-cross-generation-v1":
            originalityState = .unknown
            originalityDetail = text("Saved-package originality evidence is incomplete. \(provenanceDetail(report, locale: locale))")
        case .live where report.noveltyPassed == true:
            originalityState = switch report.authoringProvenance.kind {
            case .unreviewed, .unknown: .unknown
            case .reviewedFixedOnly, .aiAuthoredOnly, .mixed: .passed
            }
            originalityDetail = text("Saved-package similarity checks passed. \(provenanceDetail(report, locale: locale))")
        case .live where report.noveltyPassed == false:
            originalityState = .pending
            originalityDetail = text("Saved-package similarity checks did not pass. \(provenanceDetail(report, locale: locale))")
        case .live, .unknown:
            originalityState = .unknown
            originalityDetail = text("Saved-package originality evidence is incomplete. \(provenanceDetail(report, locale: locale))")
        }

        let coverageText = report.difficultyReviewCoverage.map {
            text("\(report.difficultyReviewedItems) of \(report.referenceDemandItems) items (\($0.formatted(.percent.precision(.fractionLength(0)).locale(locale))))")
        } ?? text("unknown item coverage")
        let validItemReview = validatedItemReview(report)
        let completeLiveReview = report.savedMode == .live
            && validItemReview
            && report.referenceDemandPassed == true
            && report.difficultyReviewCoverage == 1.0
            && report.difficultyApprovedItems == report.referenceDemandItems
            && report.difficultyReasoningFitItems == report.difficultyReviewedItems
            && report.difficultyContextFitItems == report.difficultyReviewedItems
            && report.difficultyShortcutFitItems == report.difficultyReviewedItems
            && report.referenceDemandFailedChecks?.isEmpty == true
        let referenceState: GenerationQualityState
        let referenceDetail: String
        if report.referenceEvidenceState == "insufficient" {
            referenceState = .insufficient
            referenceDetail = text("Reference calibration is insufficient; item review covers \(coverageText).")
                + " " + report.evidenceGaps.joined(separator: " ")
        } else if report.savedMode == .preview {
            referenceState = .preview
            referenceDetail = text("Aggregate profile fit is preview-only; validated item depth covers \(coverageText).")
        } else if completeLiveReview {
            referenceState = .passed
            referenceDetail = text("Aggregate profile fit passed and validated item depth covers \(coverageText).")
        } else if report.savedMode == .unknown
                    || report.referenceDemandPassed == nil
                    || !validItemReview {
            referenceState = .unknown
            referenceDetail = text("Saved profile or item-review coverage is missing; item depth is unknown.")
        } else {
            referenceState = .pending
            referenceDetail = text("Profile fit or validated item coverage is incomplete: \(coverageText).")
        }
        let pathState: GenerationQualityState
        if report.pathEvidenceState == "insufficient" {
            pathState = .insufficient
        } else {
            pathState = switch report.candidatePathEvidencePassed {
            case .some(true): .passed
            case .some(false): .pending
            case nil: .unknown
            }
        }
        let pathDetail = report.pathEvidenceState == "insufficient"
            ? text("Candidate-path reference qualification is insufficient. A structurally valid practice bank is not calibrated or externally qualified.")
            : (report.candidatePathEvidencePassed.map {
            $0 ? text("Candidate-path evidence passed.") : text("Candidate-path evidence needs review.")
        } ?? text("Candidate-path and focused-bank evidence is not present in this package."))
        let identity = [report.identity.subject, report.identity.paper]
            .compactMap { $0 }
            .joined(separator: " / ")
        return GenerationQualityPresentation(
            originalityState: originalityState,
            originalityDetail: originalityDetail,
            referenceDemandState: referenceState,
            referenceDemandDetail: referenceDetail,
            pathEvidenceState: pathState,
            pathEvidenceDetail: pathDetail,
            diagnosticLines: [
                "Saved package: \(identity.isEmpty ? "Unknown" : identity)",
                "Saved seed: \(report.identity.seed.map(String.init) ?? "Unknown")",
                "Saved job: \(report.identity.jobID ?? "Unknown")",
                "Saved mode: \(report.savedMode.rawValue)",
                "Saved form: \(report.identity.formID ?? "Unknown")",
                "Saved generator: \(report.identity.generatorID ?? "Unknown") \(report.identity.generatorVersion ?? "")".trimmingCharacters(in: .whitespaces),
                "Originality (\(originalityState.title)): \(originalityDetail)",
                "Reference demand: \(referenceDetail)",
                "Candidate paths: \(pathDetail)",
                "Valid paper routes: \(report.candidatePathCount.map(String.init) ?? "Unknown"); candidate marks: \(report.candidateMarkRange.map { $0.map(String.init).joined(separator: " to ") } ?? "Unknown"); printed marks: \(report.printedMarks.map(String.init) ?? "Unknown"). Times are estimates; no learner timings are recorded.",
            ]
        )
    }

    private static func provenanceDetail(_ report: GenerationQualityReport, locale: Locale) -> String {
        func text(_ resource: LocalizedStringResource) -> String {
            String(localized: InterfaceText.localizedResource(resource, locale: locale))
        }
        let provenance = report.authoringProvenance
        switch provenance.kind {
        case .reviewedFixedOnly:
            return text("All content follows reviewed fixed contracts; no AI-authored wording is recorded.")
        case .aiAuthoredOnly:
            return text("The package records AI-authored content; review coverage remains a separate check.")
        case .mixed:
            if let stems = provenance.aiAuthoredStemItems, stems > 0 {
                return text("Mixed provenance includes \(stems) stem edit(s) and reviewed fixed contracts; a stem edit is not full-question authorship.")
            }
            return text("The package records mixed authored and reviewed fixed content.")
        case .unreviewed:
            return text("The package records built-in or unreviewed content, not reviewed originality.")
        case .unknown:
            return text("Authoring provenance is unknown.")
        }
    }

    private static func validatedItemReview(_ report: GenerationQualityReport) -> Bool {
        guard report.itemCount > 0,
              report.referenceDemandItems == report.itemCount,
              let approved = report.difficultyApprovedItems,
              let coverage = report.difficultyReviewCoverage,
              report.referenceDemandFailedChecks != nil,
              report.difficultyReviewedItems >= 0,
              approved >= 0,
              approved <= report.difficultyReviewedItems,
              report.difficultyReviewedItems <= report.referenceDemandItems,
              (0.0 ... 1.0).contains(coverage),
              let reasoningFit = report.difficultyReasoningFitItems,
              reasoningFit >= 0,
              reasoningFit <= report.difficultyReviewedItems,
              let contextFit = report.difficultyContextFitItems,
              contextFit >= 0,
              contextFit <= report.difficultyReviewedItems,
              let shortcutFit = report.difficultyShortcutFitItems,
              shortcutFit >= 0,
              shortcutFit <= report.difficultyReviewedItems
        else { return false }
        let expectedCoverage = Double(report.difficultyReviewedItems)
            / Double(report.referenceDemandItems)
        return abs(coverage - expectedCoverage) < 0.000_001
    }
}
