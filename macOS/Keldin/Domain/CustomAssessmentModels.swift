// Decode backend records and represent the selections shown by the app.

// Source metadata and layout observations for custom assessments.

import Foundation

struct CustomAssessmentSourceMetadata: Decodable, Equatable {
    enum Role: String, Decodable {
        case questionPaper = "question-paper"
        case markScheme = "mark-scheme"
        case syllabus
        case expectedContent = "expected-content"
    }

    let role: Role
    let sha256: String
    let pageCount: Int
    let pagesWithoutText: [Int]

    var isValid: Bool {
        (1...80).contains(pageCount)
            && sha256.utf8.count == 64
            && sha256.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
            && pagesWithoutText.count <= pageCount
            && pagesWithoutText == Array(Set(pagesWithoutText)).sorted()
            && pagesWithoutText.allSatisfy { (1...pageCount).contains($0) }
    }
}

struct CustomPageLayoutObservation: Decodable, Equatable {
    struct Layout: Decodable, Equatable {
        let heading: String
        let columns: Int
        let questionMarkers: [String]
        let responseSpace: [String]
        let figures: [String]

        var isValid: Bool {
            heading.unicodeScalars.count <= 160
                && (1...4).contains(columns)
                && questionMarkers.count <= 40
                && questionMarkers.allSatisfy { (1...24).contains($0.unicodeScalars.count) }
                && responseSpace.count <= 40
                && responseSpace.allSatisfy { ["ruled lines", "dotted lines", "box", "blank", "none"].contains($0) }
                && figures.count <= 24
                && figures.allSatisfy { ["table", "graph", "diagram", "image", "other"].contains($0) }
        }
    }

    let role: CustomAssessmentSourceMetadata.Role
    let sha256: String
    let page: Int
    let model: String
    let layout: Layout

    var isValid: Bool {
        (1...80).contains(page)
            && sha256.utf8.count == 64
            && sha256.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
            && model.range(of: #"\A[A-Za-z0-9][A-Za-z0-9_.-]{0,95}:[A-Za-z0-9_.-]{1,80}\z"#, options: .regularExpression) != nil
            && layout.isValid
    }
}
