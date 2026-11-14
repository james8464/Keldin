#if DEBUG
import SwiftUI
import UniformTypeIdentifiers

struct CustomAssessmentPreview: View {
    private struct Source: Identifiable {
        let id = UUID()
        let url: URL
        var role: CustomAssessmentSourceMetadata.Role = .questionPaper
    }

    private struct InspectionRow: Identifiable {
        let id: UUID
        let name: String
        let metadata: CustomAssessmentSourceMetadata
    }

    @EnvironmentObject private var application: ApplicationCoordinator
    @State private var sources: [Source] = []
    @State private var results: [InspectionRow] = []
    @State private var showPicker = false
    @State private var inspecting = false
    @State private var errorMessage: String?

    private var canInspect: Bool {
        sources.filter { $0.role == .questionPaper }.count >= 3
            && !inspecting && !application.isRunning && !application.isImportingPreviousData
            && !application.benchmarkCoordinator.isRunning
    }

    var body: some View {
        Form {
            Section("Source PDFs") {
                Text("Add at least three different past question papers. You can also add mark schemes, a syllabus or expected content.")
                Text("Inspection stays on this Mac. This preview does not generate papers.")
                    .foregroundStyle(.secondary)
                ForEach($sources) { $source in
                    let sourceID = source.id
                    HStack {
                        Text(source.url.lastPathComponent)
                            .lineLimit(1)
                        Spacer()
                        Picker("Role", selection: $source.role) {
                            Text("Question paper").tag(CustomAssessmentSourceMetadata.Role.questionPaper)
                            Text("Mark scheme").tag(CustomAssessmentSourceMetadata.Role.markScheme)
                            Text("Syllabus").tag(CustomAssessmentSourceMetadata.Role.syllabus)
                            Text("Expected content").tag(CustomAssessmentSourceMetadata.Role.expectedContent)
                        }
                        .labelsHidden()
                        .accessibilityLabel("Source role")
                        Button("Remove", role: .destructive) {
                            sources.removeAll { $0.id == sourceID }
                        }
                    }
                    .disabled(inspecting)
                }
                Button("Add PDFs…") { showPicker = true }
                    .disabled(inspecting || sources.count >= 12)
                Button("Inspect PDFs", action: inspect)
                    .disabled(!canInspect)
                if inspecting {
                    ProgressView("Checking PDFs…")
                }
                if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle")
                }
            }
            if !results.isEmpty {
                Section("Inspection results") {
                    ForEach(results) { result in
                        VStack(alignment: .leading, spacing: 4) {
                            LabeledContent {
                                Text(result.metadata.pageCount, format: .number)
                            } label: {
                                Text("Pages in \(result.name)")
                            }
                            if result.metadata.pagesWithoutText.count == result.metadata.pageCount {
                                Text("No extractable text. Visual review is needed before using this source.")
                                    .foregroundStyle(.secondary)
                            } else if !result.metadata.pagesWithoutText.isEmpty {
                                Text("Pages without extractable text: \(result.metadata.pagesWithoutText.map { $0.formatted() }.joined(separator: ", "))")
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
        .formStyle(.grouped)
        .navigationTitle("Custom Paper Preview")
        .fileImporter(isPresented: $showPicker, allowedContentTypes: [.pdf], allowsMultipleSelection: true) { result in
            guard case let .success(urls) = result else {
                errorMessage = String(localized: "Could not open the selected files.")
                return
            }
            var known = Set(sources.map { $0.url.standardizedFileURL })
            let added = urls.filter { known.insert($0.standardizedFileURL).inserted }
            guard sources.count + added.count <= 12 else {
                errorMessage = String(localized: "Choose no more than twelve files.")
                return
            }
            sources += added.map { Source(url: $0) }
        }
        .onChange(of: sources.map { CustomAssessmentSelection(role: $0.role, url: $0.url) }) {
            results = []
            errorMessage = nil
        }
    }

    private func inspect() {
        guard canInspect else { return }
        let snapshot = sources
        let selection = snapshot.map { CustomAssessmentSelection(role: $0.role, url: $0.url) }
        inspecting = true
        results = []
        errorMessage = nil
        Task {
            defer { inspecting = false }
            do {
                let metadata = try await application.inspectCustomAssessmentSources(selection)
                results = zip(snapshot, metadata).map { source, result in
                    InspectionRow(id: source.id, name: source.url.lastPathComponent, metadata: result)
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
#endif
