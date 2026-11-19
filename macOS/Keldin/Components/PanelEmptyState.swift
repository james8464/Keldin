// Present the empty state used by workspace panels.

import SwiftUI

struct PanelEmptyState: View {
    @Environment(\.locale) private var locale
    let title: LocalizedStringResource
    let message: LocalizedStringResource
    let systemImage: String

    var body: some View {
        ContentUnavailableView {
            Label { Text(InterfaceText.localizedResource(title, locale: locale)) } icon: { Image(systemName: systemImage) }
                .symbolRenderingMode(.hierarchical)
        } description: {
            Text(InterfaceText.localizedResource(message, locale: locale))
        }
        .frame(maxWidth: .infinity)
    }
}
