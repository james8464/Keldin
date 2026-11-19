// Decode backend records and represent the selections shown by the app.

// Generated document records shared by history and previews.

import Foundation

struct GeneratedFile: Identifiable, Codable, Equatable {
    let id: UUID
    let role: String
    let url: URL
    let createdAt: Date
    let subject: String
    let paper: String

    init(
        id: UUID = UUID(),
        role: String,
        url: URL,
        createdAt: Date = Date(),
        subject: String = "",
        paper: String = ""
    ) {
        self.id = id
        self.role = role
        self.url = url
        self.createdAt = createdAt
        self.subject = subject
        self.paper = paper
    }

    var exists: Bool {
        FileManager.default.fileExists(atPath: url.path)
    }

    var title: String {
        switch role {
        case "question_paper": "Question Paper"
        case "source_booklet": "Source Booklet"
        case "mark_scheme": "Mark Scheme"
        case "assessment_package": "Assessment Package"
        case "package_manifest": "Package Manifest"
        case "preliminary_material": "Preliminary Material"
        case "electronic_answer_document": "Electronic Answer Document"
        case "skeleton_program": "Skeleton Program"
        case "data_file": "Practice Data"
        default: role.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    var paperDescription: String {
        [subject, paper].filter { !$0.isEmpty }.joined(separator: " · ")
    }
}
