import AppKit
import SwiftUI
import XCTest
@testable import Keldin

final class DocumentPickerTests: XCTestCase {
    @MainActor
    func testNativeMenuReportsOnlyItsOwnTrackingBoundary() throws {
        let files = fixtures(count: 2)
        var events: [Bool] = []
        let hosting = NSHostingController(rootView: DocumentPickerView(
            files: files, selection: .constant(files[0].id),
            onTrackingChanged: { events.append($0) }
        ))
        hosting.view.frame = NSRect(x: 0, y: 0, width: 400, height: 44)
        hosting.view.layoutSubtreeIfNeeded()
        let picker = try XCTUnwrap(nativePicker(in: hosting.view))
        let menu = try XCTUnwrap(picker.menu)

        NotificationCenter.default.post(name: NSMenu.didBeginTrackingNotification, object: NSMenu())
        XCTAssertTrue(events.isEmpty)
        NotificationCenter.default.post(name: NSMenu.didBeginTrackingNotification, object: menu)
        XCTAssertEqual(events, [true])
        NotificationCenter.default.post(name: NSMenu.didEndTrackingNotification, object: menu)
        XCTAssertEqual(events, [true, false])
    }

    @MainActor
    func testNativeMenuCommitsSelectionBeforeReturning() throws {
        let files = fixtures(count: 2)
        var selection = files[0].id
        let hosting = NSHostingController(rootView: DocumentPickerView(
            files: files, selection: Binding(get: { selection }, set: { selection = $0 })
        ))
        hosting.view.frame = NSRect(x: 0, y: 0, width: 400, height: 44)
        hosting.view.layoutSubtreeIfNeeded()
        let picker = try XCTUnwrap(nativePicker(in: hosting.view))
        let action = try XCTUnwrap(picker.action)

        for index in [1, 0] {
            picker.selectItem(at: index)
            XCTAssertTrue(picker.sendAction(action, to: picker.target))
            XCTAssertEqual(selection, files[index].id, "Commands may run before the next run loop turn")
        }
    }

    @MainActor
    func testNativeMenuKeepsFilesWithIdenticalLabelsSelectable() throws {
        let files = ["/fixture/a.pdf", "/fixture/b.pdf"].map {
            GeneratedFile(
                role: "question_paper", url: URL(fileURLWithPath: $0),
                createdAt: Date(timeIntervalSince1970: 1_793_232_000),
                subject: "Accounting", paper: "Paper 1"
            )
        }
        let hosting = NSHostingController(rootView: DocumentPickerView(
            files: files, selection: .constant(files[1].id)
        ))
        hosting.view.frame = NSRect(x: 0, y: 0, width: 400, height: 44)
        hosting.view.layoutSubtreeIfNeeded()
        let picker = try XCTUnwrap(nativePicker(in: hosting.view))
        XCTAssertEqual(picker.numberOfItems, 2)
        XCTAssertEqual(picker.item(at: 0)?.title, picker.item(at: 1)?.title)
        XCTAssertEqual(picker.selectedItem?.representedObject as? UUID, files[1].id)
        XCTAssertEqual(picker.toolTip, files[1].url.path)
    }

    @MainActor
    private func nativePicker(in view: NSView) -> NSPopUpButton? {
        if let picker = view as? NSPopUpButton { return picker }
        for child in view.subviews {
            if let picker = nativePicker(in: child) { return picker }
        }
        return nil
    }

    @MainActor
    func testLargeLibrariesKeepNativeSelectorWithinProposedWidth() throws {
        for count in [30, 60] {
            let files = fixtures(count: count)
            for width in [320.0, 900.0] {
                let hosting = NSHostingController(rootView: DocumentPickerView(
                    files: files, selection: .constant(files[0].id)
                ))
                let measured = hosting.sizeThatFits(in: CGSize(width: width, height: 80))
                hosting.view.frame = NSRect(x: 0, y: 0, width: width, height: measured.height)
                hosting.view.layoutSubtreeIfNeeded()
                XCTAssertGreaterThan(measured.width, 0)
                XCTAssertLessThanOrEqual(measured.width, width + 1, "\(count) documents at \(width) points")
                XCTAssertLessThan(measured.height, 80)
            }
        }
    }

    @MainActor
    func testSegmentedReferenceCannotFitTheSameLargeHistory() {
        let files = fixtures(count: 60)
        let hosting = NSHostingController(rootView:
            Picker("Document", selection: Binding.constant(files[0].id)) {
                ForEach(files) { Text($0.title).tag($0.id) }
            }.pickerStyle(.segmented).labelsHidden()
        )
        for width in [320.0, 900.0] {
            XCTAssertGreaterThan(hosting.sizeThatFits(in: CGSize(width: width, height: 80)).width, width)
        }
    }

    @MainActor
    func testLabelsIncludeLocalisedRoleStoredContextAndLocalisedDate() {
        let file = fixtures(count: 1)[0]
        let english = DocumentPickerView.label(for: file, locale: Locale(identifier: "en_GB"))
        let french = DocumentPickerView.label(for: file, locale: Locale(identifier: "fr_FR"))
        XCTAssertTrue(english.contains("Question Paper"))
        XCTAssertTrue(french.contains("Sujet"))
        for label in [english, french] {
            XCTAssertTrue(label.contains("Accounting"))
            XCTAssertTrue(label.contains("Paper 1"))
            XCTAssertTrue(label.contains("2026"))
            XCTAssertFalse(label.contains(file.id.uuidString))
        }
        XCTAssertNotEqual(english, french)
        for locale in [Locale(identifier: "en_GB"), Locale(identifier: "fr_FR")] {
            let date = file.createdAt.formatted(.dateTime.year().month(.abbreviated).day().hour().minute().second().locale(locale))
            XCTAssertTrue(DocumentPickerView.label(for: file, locale: locale).contains(date))
        }
    }

    @MainActor
    func testRepeatedRolesKeepDistinctStoredIdentitiesAndLabels() {
        let files = fixtures(count: 60)
        XCTAssertEqual(Set(files.map(\.id)).count, 60)
        XCTAssertEqual(Set(files.map { DocumentPickerView.label(for: $0, locale: Locale(identifier: "en_GB")) }).count, 60)
    }

    private func fixtures(count: Int) -> [GeneratedFile] {
        (0 ..< count).map { index in
            GeneratedFile(
                role: index.isMultiple(of: 2) ? "question_paper" : "mark_scheme",
                url: URL(fileURLWithPath: "/fixture/paper-\(index).pdf"),
                createdAt: Date(timeIntervalSince1970: 1_793_232_000 + Double(index * 60)),
                subject: "Accounting", paper: "Paper 1"
            )
        }
    }

}
