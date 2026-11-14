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
        let selection: CustomAssessmentSelection
        let metadata: CustomAssessmentSourceMetadata
    }

    @EnvironmentObject private var application: ApplicationCoordinator
    @State private var sources: [Source] = []
    @State private var results: [InspectionRow] = []
    @State private var showPicker = false
    @State private var inspecting = false
    @State private var errorMessage: String?
    @State private var selectedSourceID: UUID?
    @State private var selectedPage = 1
    @State private var observation: CustomPageLayoutObservation?
    @State private var layoutError: String?

    private var controlsLocked: Bool { inspecting || application.isObservingCustomPage }
    private var selectedResult: InspectionRow? { results.first { $0.id == selectedSourceID } }

    private var canInspect: Bool {
        sources.filter { $0.role == .questionPaper }.count >= 3
            && !controlsLocked && !application.isRunning && !application.isImportingPreviousData
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
                    .disabled(controlsLocked)
                }
                Button("Add PDFs…") { showPicker = true }
                    .disabled(controlsLocked || sources.count >= 12)
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
                Section("Page layout") {
                    Text("Inspect one page with the Ollama model selected in Settings. Use a model that accepts images and runs on this Mac.")
                        .foregroundStyle(.secondary)
                    LabeledContent("Ollama model") {
                        Text(verbatim: application.selectedModel)
                    }
                    Group {
                        Picker("Source", selection: $selectedSourceID) {
                            ForEach(results) { result in
                                Text(verbatim: result.name).tag(Optional(result.id))
                            }
                        }
                        if let result = selectedResult, result.metadata.pageCount > 1 {
                            Stepper(value: $selectedPage, in: 1...result.metadata.pageCount) {
                                Text("Page \(selectedPage) of \(result.metadata.pageCount)")
                            }
                        }
                    }
                    .disabled(controlsLocked)
                    Button("Check Layout") { checkLayout() }
                        .disabled(
                            selectedResult == nil || controlsLocked || application.isRunning
                                || application.isImportingPreviousData || application.benchmarkCoordinator.isRunning
                        )
                    if application.isObservingCustomPage {
                        ProgressView("Checking page layout…")
                    }
                    if let layoutError {
                        Label(layoutError, systemImage: "exclamationmark.triangle")
                    }
                    if let observation {
                        PageLayoutResultView(observation: observation)
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
            resetLayout()
        }
        .onChange(of: selectedSourceID) {
            selectedPage = 1
            resetLayout()
        }
        .onChange(of: selectedPage) { resetLayout() }
    }

    private func inspect() {
        guard canInspect else { return }
        let snapshot = sources
        let selection = snapshot.map { CustomAssessmentSelection(role: $0.role, url: $0.url) }
        inspecting = true
        results = []
        selectedPage = 1
        errorMessage = nil
        resetLayout()
        Task {
            defer { inspecting = false }
            do {
                let metadata = try await application.inspectCustomAssessmentSources(selection)
                results = zip(snapshot, metadata).map { source, result in
                    InspectionRow(
                        id: source.id,
                        name: source.url.lastPathComponent,
                        selection: CustomAssessmentSelection(role: source.role, url: source.url),
                        metadata: result
                    )
                }
                selectedSourceID = results.first?.id
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    private func resetLayout() {
        observation = nil
        layoutError = nil
    }

    private func checkLayout() {
        guard let result = selectedResult else { return }
        let page = selectedPage
        resetLayout()
        Task {
            do {
                observation = try await application.observeCustomPage(
                    page, of: result.selection, verified: result.metadata
                )
            } catch {
                layoutError = error.localizedDescription
            }
        }
    }
}

private struct PageLayoutResultView: View {
    let observation: CustomPageLayoutObservation

    var body: some View {
        Text("Draft observation. Compare it with the original PDF.")
            .foregroundStyle(.secondary)
        LabeledContent("Analyzed with") { Text(verbatim: observation.model) }
        LabeledContent("Page and columns") {
            Text("Page \(observation.page), \(observation.layout.columns) columns")
        }
        if !observation.layout.heading.isEmpty {
            LabeledContent("Heading") { Text(verbatim: observation.layout.heading) }
        }
        if !observation.layout.questionMarkers.isEmpty {
            LabeledContent("Question markers") {
                Text(verbatim: observation.layout.questionMarkers.formatted(.list(type: .and)))
            }
        }
        if !observation.layout.responseSpace.isEmpty {
            LabeledContent("Response space") {
                Text(verbatim: observation.layout.responseSpace.formatted(.list(type: .and)))
            }
        }
        if !observation.layout.figures.isEmpty {
            LabeledContent("Figures") {
                Text(verbatim: observation.layout.figures.formatted(.list(type: .and)))
            }
        }
    }
}
#endif
