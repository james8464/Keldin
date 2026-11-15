import AppKit
import SwiftUI

struct DocumentPickerView: NSViewRepresentable {
    @Environment(\.locale) private var locale
    let files: [GeneratedFile]
    @Binding var selection: GeneratedFile.ID
    var onTrackingChanged: (Bool) -> Void = { _ in }

    func makeCoordinator() -> Coordinator {
        Coordinator(selection: $selection, onTrackingChanged: onTrackingChanged)
    }

    func makeNSView(context: Context) -> NSPopUpButton {
        let button = NSPopUpButton(frame: .zero, pullsDown: false)
        button.target = context.coordinator
        button.action = #selector(Coordinator.selectDocument(_:))
        button.lineBreakMode = .byTruncatingMiddle
        if let menu = button.menu {
            for name in [NSMenu.didBeginTrackingNotification, NSMenu.didEndTrackingNotification] {
                NotificationCenter.default.addObserver(
                    context.coordinator, selector: #selector(Coordinator.trackingChanged(_:)), name: name, object: menu
                )
            }
        }
        return button
    }

    func updateNSView(_ button: NSPopUpButton, context: Context) {
        let coordinator = context.coordinator
        coordinator.selection = $selection
        coordinator.onTrackingChanged = onTrackingChanged
        let entries = files.map {
            Entry(id: $0.id, title: Self.label(for: $0, locale: locale), path: $0.url.path)
        }
        if coordinator.entries != entries {
            coordinator.entries = entries
            button.removeAllItems()
            for (index, entry) in entries.enumerated() {
                // The popup deduplicates on insertion by title, but two files can share a label.
                button.addItem(withTitle: entry.id.uuidString)
                let item = button.item(at: index)
                item?.title = entry.title
                item?.toolTip = entry.path
                item?.representedObject = entry.id
            }
        }
        let index = entries.firstIndex { $0.id == selection }
        if button.indexOfSelectedItem != index ?? -1 {
            button.selectItem(at: index ?? -1)
        }
        button.toolTip = index.map { entries[$0].path }
        button.setAccessibilityLabel(
            String(localized: InterfaceText.localizedResource("Document", locale: locale))
        )
    }

    static func dismantleNSView(_ button: NSPopUpButton, coordinator: Coordinator) {
        NotificationCenter.default.removeObserver(coordinator)
    }

    func sizeThatFits(_ proposal: ProposedViewSize, nsView: NSPopUpButton, context: Context) -> CGSize? {
        let ideal = nsView.intrinsicContentSize
        return CGSize(width: min(ideal.width, proposal.width ?? ideal.width), height: ideal.height)
    }

    struct Entry: Equatable {
        let id: GeneratedFile.ID
        let title: String
        let path: String
    }

    @MainActor
    final class Coordinator: NSObject {
        var selection: Binding<GeneratedFile.ID>
        var onTrackingChanged: (Bool) -> Void
        var entries: [Entry] = []

        init(selection: Binding<GeneratedFile.ID>, onTrackingChanged: @escaping (Bool) -> Void) {
            self.selection = selection
            self.onTrackingChanged = onTrackingChanged
        }

        @objc func trackingChanged(_ event: Notification) {
            onTrackingChanged(event.name == NSMenu.didBeginTrackingNotification)
        }

        @objc func selectDocument(_ sender: NSPopUpButton) {
            guard let id = sender.selectedItem?.representedObject as? GeneratedFile.ID,
                  selection.wrappedValue != id else { return }
            // Commit at the native menu action, before a subsequent document command.
            selection.wrappedValue = id
        }
    }

    static func label(for file: GeneratedFile, locale: Locale) -> String {
        let role = String(localized: InterfaceText.localizedResource(file.titleResource, locale: locale))
        let date = file.createdAt.formatted(
            .dateTime.year().month(.abbreviated).day().hour().minute().second().locale(locale)
        )
        return [role, file.subject, file.paper, date]
            .filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            .joined(separator: " · ")
    }
}
